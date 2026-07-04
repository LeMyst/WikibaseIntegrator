"""
Login class for Wikidata. Takes authentication parameters and stores the session cookies and edit tokens.
"""
import logging
import time
import webbrowser
from typing import Any, cast
from urllib.parse import parse_qs, urlencode

import requests
from oauthlib.oauth2 import BackendApplicationClient, InvalidClientError
from requests import Session
from requests.cookies import RequestsCookieJar
from requests_oauthlib import OAuth1 as OAuth1Auth
from requests_oauthlib import OAuth1Session, OAuth2Session

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import get_user_agent

log = logging.getLogger(__name__)


class _Login:
    """
    A class which handles the login to Wikidata and the generation of edit-tokens
    """

    @wbi_backoff()
    def __init__(self, session: Session | None = None, mediawiki_api_url: str | None = None, token_renew_period: int = 1800, user_agent: str | None = None):
        """
        This class handles several types of login procedures. Either use user and pwd authentication or OAuth.
        Wikidata clientlogin can also be used. If using one method, do NOT pass parameters for another method.

        :param session: A requests.Session instance
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        """

        self.session: Session = session or Session()
        self.mediawiki_api_url: str = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        self.token_renew_period: int = token_renew_period

        self.edit_token: str | None = None
        self.instantiation_time: float = time.time()

        self.session.headers.update({
            'User-Agent': get_user_agent(user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None))
        })

        self.generate_edit_credentials()

    def generate_edit_credentials(self) -> RequestsCookieJar:
        """
        Request an edit token and update the cookie_jar in order to add the session cookie

        :return: Returns a json with all relevant cookies, aka cookie jar
        """
        params = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'csrf',
            'format': 'json'
        }
        response = self.session.get(url=self.mediawiki_api_url, params=params, timeout=config['TIMEOUT']).json()
        if 'error' in response:
            raise LoginError(f"Login failed ({response['error']['code']}). Message: '{response['error']['info']}'")
        if response['query']['tokens']['csrftoken'] == '+\\':
            raise LoginError("Login failed. An anonymous token was returned.")
        self.edit_token = response['query']['tokens']['csrftoken']

        return self.session.cookies

    def get_edit_cookie(self) -> RequestsCookieJar:
        """
        Can be called in order to retrieve the cookies from an instance of wbi_login.Login

        :return: Returns a json with all relevant cookies, aka cookie jar
        """
        if (time.time() - self.instantiation_time) > self.token_renew_period:
            self.generate_edit_credentials()
            self.instantiation_time = time.time()

        return self.session.cookies

    def get_edit_token(self) -> str | None:
        """
        Can be called in order to retrieve the edit token from an instance of wbi_login.Login

        :return: returns the edit token
        """
        if not self.edit_token or (time.time() - self.instantiation_time) > self.token_renew_period:
            self.generate_edit_credentials()
            self.instantiation_time = time.time()

        return self.edit_token

    def get_session(self) -> Session:
        """
        Returns the requests.Session object used for the login.

        :return: Object of type requests.Session()
        """
        return self.session

    def reauthenticate(self) -> None:
        """
        Recover from a session that the server has invalidated (e.g. MediaWiki returning
        'assertuserfailed'/'assertbotfailed'/'notloggedin' on an otherwise well-formed request, see #902).

        Simply asking for a new CSRF token via generate_edit_credentials() cannot resurrect a session the
        server has already dropped, since that call is itself authenticated by the same (now invalid)
        session cookies. This default implementation is only adequate for auth methods where
        generate_edit_credentials() actually re-establishes the underlying credentials (OAuth2, which
        refreshes its access token first) or where authentication is per-request rather than session-based
        (OAuth1). Login and Clientlogin override this to redo the full username/password login.
        """
        self.generate_edit_credentials()
        self.instantiation_time = time.time()


class OAuth2(_Login):
    @wbi_backoff()
    def __init__(self, consumer_token: str | None = None, consumer_secret: str | None = None, mediawiki_api_url: str | None = None, mediawiki_rest_url: str | None = None, token_renew_period: int = 1800,
                 user_agent: str | None = None):
        """
        This class is used to interact with the OAuth2 API.

        :param consumer_token: The consumer token
        :param consumer_secret: The consumer secret
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param mediawiki_rest_url: The URL to the MediaWiki REST API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        """

        mediawiki_rest_url = str(mediawiki_rest_url or config['MEDIAWIKI_REST_URL'])

        self.consumer_token = consumer_token
        self.consumer_secret = consumer_secret
        self.access_token_url = mediawiki_rest_url + '/oauth2/access_token'

        session = OAuth2Session(client=BackendApplicationClient(client_id=consumer_token))
        # The access token is fetched (and later refreshed) by generate_edit_credentials(), invoked by the parent __init__.
        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)

    def _fetch_access_token(self) -> None:
        """
        (Re)fetch the OAuth2 access token.

        The client-credentials grant used here does not issue a refresh token, so the short-lived access token
        (~4h on Wikimedia) is simply re-fetched. Called on every credentials renewal to keep long-running bots alive.
        """
        headers = {'User-Agent': self.session.headers.get('User-Agent', get_user_agent())}
        try:
            cast(OAuth2Session, self.session).fetch_token(token_url=self.access_token_url, client_id=self.consumer_token, client_secret=self.consumer_secret, headers=headers,
                                                          timeout=config['TIMEOUT'])
        except InvalidClientError as err:
            raise LoginError(err) from err

    def generate_edit_credentials(self) -> RequestsCookieJar:
        # Refresh the access token before requesting the CSRF token: the parent renews credentials every
        # token_renew_period seconds, so this keeps the OAuth2 session authenticated past the token expiry.
        self._fetch_access_token()
        return super().generate_edit_credentials()


class OAuth1(_Login):

    @wbi_backoff()
    def __init__(self, consumer_token: str | None = None, consumer_secret: str | None = None, access_token: str | None = None, access_secret: str | None = None, callback_url: str = 'oob',
                 mediawiki_api_url: str | None = None, mediawiki_index_url: str | None = None, token_renew_period: int = 1800, user_agent: str | None = None):
        """
        This class is used to interact with the OAuth1 API.

        :param consumer_token: The consumer token
        :param consumer_secret: The consumer secret
        :param access_token: The access token (optional )
        :param access_secret: The access secret (optional)
        :param callback_url: The callback URL used to finalize the handshake
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param mediawiki_index_url: The URL to the MediaWiki index (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        """

        mediawiki_index_url = str(mediawiki_index_url or config['MEDIAWIKI_INDEX_URL'])

        if access_token and access_secret:
            # OAuth procedure, based on https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers#Python
            session = OAuth1Session(client_key=consumer_token, client_secret=consumer_secret, resource_owner_key=access_token, resource_owner_secret=access_secret)
            super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)
        else:
            # Oauth procedure, based on https://www.mediawiki.org/wiki/OAuth/For_Developers
            self.consumer_token = consumer_token
            self.consumer_secret = consumer_secret
            self.mediawiki_index_url = mediawiki_index_url
            self.mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
            self.token_renew_period = token_renew_period
            self.user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

            # Step 1: Initiate -- ask MediaWiki for a temporary key/secret for the user
            auth = OAuth1Auth(consumer_token, client_secret=consumer_secret, callback_uri=callback_url)
            response = requests.post(url=mediawiki_index_url, params={'title': "Special:OAuth/initiate"}, auth=auth, headers={'User-Agent': get_user_agent(self.user_agent)}, timeout=config['TIMEOUT'])

            request_token = self._parse_token_response(response.text)
            self.request_token_key = request_token['oauth_token']
            self.request_token_secret = request_token['oauth_token_secret']

            # redirect -> authorization -> callback url
            params = {'title': "Special:OAuth/authenticate", 'oauth_token': self.request_token_key, 'oauth_consumer_key': consumer_token}
            self.redirect = mediawiki_index_url + '?' + urlencode(params)

    @staticmethod
    def _parse_token_response(content: str) -> dict[str, str]:
        if content.startswith("Error: "):
            raise LoginError(content[len("Error: "):])

        credentials = parse_qs(content)
        if not credentials or 'oauth_token' not in credentials or 'oauth_token_secret' not in credentials:
            raise LoginError(f"MediaWiki response lacks token information: {content!r}")

        return {'oauth_token': credentials['oauth_token'][0], 'oauth_token_secret': credentials['oauth_token_secret'][0]}

    def continue_oauth(self, oauth_callback_data: str | None = None) -> None:
        """
        Continuation of OAuth procedure. Method must be explicitly called in order to complete OAuth. This allows
        external entities, e.g. websites, to provide tokens through callback URLs directly.

        :param oauth_callback_data: The callback URL received to a Web app
        :return:
        """

        if not oauth_callback_data:
            webbrowser.open(self.redirect)
            oauth_callback_data = input("Callback URL: ")

        # input the url from redirect after authorization
        response_qs = oauth_callback_data.split('?')[-1]
        callback_data = parse_qs(response_qs)

        if not callback_data or 'oauth_token' not in callback_data or 'oauth_verifier' not in callback_data:
            raise LoginError(f"Query string lacks token information: {callback_data!r}")

        request_token_key = callback_data['oauth_token'][0]
        verifier = callback_data['oauth_verifier'][0]

        if self.request_token_key != request_token_key:
            raise LoginError(f"Unexpected request token key {request_token_key!r}, expected {self.request_token_key!r}.")

        # Step 3: Complete -- obtain authorized key/secret for "resource owner"
        auth = OAuth1Auth(self.consumer_token, client_secret=self.consumer_secret, resource_owner_key=self.request_token_key, resource_owner_secret=self.request_token_secret, verifier=verifier)
        response = requests.post(url=self.mediawiki_index_url, params={'title': "Special:OAuth/token"}, auth=auth, headers={'User-Agent': get_user_agent(self.user_agent)}, timeout=config['TIMEOUT'])

        access_token = self._parse_token_response(response.text)

        # input the access token to return a csrf (edit) token
        session = OAuth1Session(client_key=self.consumer_token, client_secret=self.consumer_secret, resource_owner_key=access_token['oauth_token'],
                                resource_owner_secret=access_token['oauth_token_secret'])
        super().__init__(session=session, token_renew_period=self.token_renew_period, user_agent=self.user_agent, mediawiki_api_url=self.mediawiki_api_url)


class Login(_Login):
    @wbi_backoff()
    def __init__(self, user: str | None = None, password: str | None = None, mediawiki_api_url: str | None = None, token_renew_period: int = 1800, user_agent: str | None = None, **kwargs: Any):
        """
        This class is used to log in with a bot password

        :param user: The user of the bot password (format <User>@<BotUser>)
        :param password: The password generated byt the MediaWiki
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        :param kwargs: Additional parameters to pass to the requests.sessions.Session.post method, such as headers or proxies.
        """

        mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)
        session = Session()

        # Kept so reauthenticate() can redo this same flow after the server invalidates the session (#902).
        self._user = user
        self._password = password
        self._login_kwargs = kwargs

        headers = {
            'User-Agent': get_user_agent(user_agent)
        }
        self._perform_login(session=session, mediawiki_api_url=mediawiki_api_url, headers=headers, **kwargs)

        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)

    def _perform_login(self, session: Session, mediawiki_api_url: str, headers: dict[str, str], **kwargs: Any) -> None:
        params_login = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login',
            'format': 'json'
        }

        allowed_kwargs = {'headers', 'proxies', 'timeout', 'verify'}
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in allowed_kwargs}
        if len(filtered_kwargs) < len(kwargs):
            log.warning("Unsupported kwargs were ignored: %s", set(kwargs) - allowed_kwargs)
        filtered_kwargs.setdefault('timeout', config['TIMEOUT'])

        # get login token
        login_token = session.post(mediawiki_api_url, data=params_login, headers=headers, **filtered_kwargs).json()['query']['tokens']['logintoken']
        params = {
            'action': 'login',
            'lgname': self._user,
            'lgpassword': self._password,
            'lgtoken': login_token,
            'format': 'json'
        }

        login_result = session.post(mediawiki_api_url, data=params, headers=headers, **filtered_kwargs).json()

        if 'login' in login_result and login_result['login']['result'] == 'Success':
            log.info("Successfully logged in as %s", login_result['login']['lgusername'])
        elif 'login' in login_result:
            raise LoginError(f"Login failed. Reason: '{login_result['login'].get('reason', login_result['login']['result'])}'")
        else:
            raise LoginError(f"Login failed. Unexpected API response: {login_result.get('error', login_result)}")

        if 'warnings' in login_result:
            log.warning("MediaWiki login warnings messages:")
            for message in login_result['warnings']:
                log.warning(f"* {message}: {login_result['warnings'][message]['*']}")

    def reauthenticate(self) -> None:
        """
        Redo the full bot-password login flow on the existing session, then refresh the CSRF token.
        See _Login.reauthenticate() for why this full re-login is needed instead of just fetching a new token.
        """
        log.warning("Session no longer valid, re-authenticating as %s", self._user)
        headers = {'User-Agent': self.session.headers.get('User-Agent', get_user_agent())}
        self._perform_login(session=self.session, mediawiki_api_url=self.mediawiki_api_url, headers=headers, **self._login_kwargs)
        self.generate_edit_credentials()
        self.instantiation_time = time.time()


class Clientlogin(_Login):
    @wbi_backoff()
    def __init__(self, user: str | None = None, password: str | None = None, mediawiki_api_url: str | None = None, token_renew_period: int = 1800, user_agent: str | None = None, **kwargs: Any):
        """
        This class is used to log in with a user account

        :param user: The username
        :param password: The password
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        :param kwargs: Additional parameters to pass to the requests.sessions.Session.post method, such as headers or proxies.
        """

        mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)
        session = Session()

        # Kept so reauthenticate() can redo this same flow after the server invalidates the session (#902).
        self._user = user
        self._password = password
        self._login_kwargs = kwargs

        headers = {
            'User-Agent': get_user_agent(user_agent)
        }
        self._perform_login(session=session, mediawiki_api_url=mediawiki_api_url, headers=headers, **kwargs)

        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)

    def _perform_login(self, session: Session, mediawiki_api_url: str, headers: dict[str, str], **kwargs: Any) -> None:
        params_login = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login',
            'format': 'json'
        }

        allowed_kwargs = {'headers', 'proxies', 'timeout', 'verify'}
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in allowed_kwargs}
        if len(filtered_kwargs) < len(kwargs):
            log.warning("Unsupported kwargs were ignored: %s", set(kwargs) - allowed_kwargs)
        filtered_kwargs.setdefault('timeout', config['TIMEOUT'])

        # get login token
        login_token = session.post(mediawiki_api_url, data=params_login, headers=headers, **filtered_kwargs).json()['query']['tokens']['logintoken']

        params = {
            'action': 'clientlogin',
            'username': self._user,
            'password': self._password,
            'logintoken': login_token,
            'loginreturnurl': 'https://example.org/',
            'format': 'json'
        }

        login_result = session.post(mediawiki_api_url, data=params, headers=headers, **filtered_kwargs).json()

        log.debug(login_result)

        if 'clientlogin' in login_result:
            clientlogin = login_result['clientlogin']
            if clientlogin['status'] != 'PASS':
                log.debug(clientlogin)
                raise LoginError(f"Login failed ({clientlogin['messagecode']}). Message: '{clientlogin['message']}'")

            log.info("Successfully logged in as %s", clientlogin['username'])
        elif 'error' in login_result:
            raise LoginError(f"Login failed ({login_result['error']['code']}). Message: '{login_result['error']['info']}'")
        else:
            raise LoginError(f"Login failed. Unexpected API response: {login_result}")

        if 'warnings' in login_result:
            log.warning("MediaWiki login warnings messages:")
            for message in login_result['warnings']:
                log.warning(f"* {message}: {login_result['warnings'][message]['*']}")

    def reauthenticate(self) -> None:
        """
        Redo the full clientlogin flow on the existing session, then refresh the CSRF token.
        See _Login.reauthenticate() for why this full re-login is needed instead of just fetching a new token.
        """
        log.warning("Session no longer valid, re-authenticating as %s", self._user)
        headers = {'User-Agent': self.session.headers.get('User-Agent', get_user_agent())}
        self._perform_login(session=self.session, mediawiki_api_url=self.mediawiki_api_url, headers=headers, **self._login_kwargs)
        self.generate_edit_credentials()
        self.instantiation_time = time.time()


class LoginError(Exception):
    """Raised when there is an issue with the login"""
