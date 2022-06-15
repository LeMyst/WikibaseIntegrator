"""
Login class for Wikidata. Takes authentication parameters and stores the session cookies and edit tokens.
"""
import logging
import time
import webbrowser
from typing import Optional

from mwoauth import ConsumerToken, Handshaker, OAuthException
from oauthlib.oauth2 import BackendApplicationClient, InvalidClientError
from requests import Session
from requests.cookies import RequestsCookieJar
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
    def __init__(self, session: Session = None, mediawiki_api_url: str = None, token_renew_period: int = 1800, user_agent: str = None):
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

        self.edit_token: Optional[str] = None
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
        response = self.session.get(url=self.mediawiki_api_url, params=params).json()
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

    def get_edit_token(self) -> Optional[str]:
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


class OAuth2(_Login):
    @wbi_backoff()
    def __init__(self, consumer_token: str = None, consumer_secret: str = None, mediawiki_api_url: str = None, mediawiki_rest_url: str = None, token_renew_period: int = 1800,
                 user_agent: str = None):
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

        session = OAuth2Session(client=BackendApplicationClient(client_id=consumer_token))
        try:
            session.fetch_token(token_url=mediawiki_rest_url + '/oauth2/access_token', client_id=consumer_token, client_secret=consumer_secret)
        except InvalidClientError as err:
            raise LoginError(err) from err
        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)


class OAuth1(_Login):

    @wbi_backoff()
    def __init__(self, consumer_token: str = None, consumer_secret: str = None, access_token: str = None, access_secret: str = None, callback_url: str = 'oob',
                 mediawiki_api_url: str = None, mediawiki_index_url: str = None, token_renew_period: int = 1800, user_agent: str = None):
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
            # Consruct a "consumer" from the key/secret provided by MediaWiki
            self.oauth1_consumer_token = ConsumerToken(consumer_token, consumer_secret)

            # Construct handshaker with wiki URI and consumer
            self.handshaker = Handshaker(mw_uri=mediawiki_index_url, consumer_token=self.oauth1_consumer_token, callback=callback_url,
                                         user_agent=get_user_agent(user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)))

            # Step 1: Initialize -- ask MediaWiki for a temp key/secret for user
            # redirect -> authorization -> callback url
            try:
                self.redirect, self.request_token = self.handshaker.initiate(callback=callback_url)
            except OAuthException as err:
                raise LoginError(err) from err

    def continue_oauth(self, oauth_callback_data: str = None) -> None:
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

        # Step 3: Complete -- obtain authorized key/secret for "resource owner"
        access_token = self.handshaker.complete(self.request_token, response_qs)

        if self.oauth1_consumer_token is None:
            raise ValueError("oauth1_consumer_token can't be None")

        # input the access token to return a csrf (edit) token
        self.session = OAuth1Session(client_key=self.oauth1_consumer_token.key, client_secret=self.oauth1_consumer_token.secret, resource_owner_key=access_token.key,
                                     resource_owner_secret=access_token.secret)
        self.generate_edit_credentials()


class Login(_Login):
    @wbi_backoff()
    def __init__(self, user: str = None, password: str = None, mediawiki_api_url: str = None, token_renew_period: int = 1800, user_agent: str = None):
        """
        This class is used to log in with a bot password

        :param user: The user of the bot password (format <User>@<BotUser>)
        :param password: The password generated byt the MediaWiki
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        """

        mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        session = Session()

        params_login = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login',
            'format': 'json'
        }

        # get login token
        login_token = session.post(mediawiki_api_url, data=params_login).json()['query']['tokens']['logintoken']

        params = {
            'action': 'login',
            'lgname': user,
            'lgpassword': password,
            'lgtoken': login_token,
            'format': 'json'
        }

        login_result = session.post(mediawiki_api_url, data=params).json()

        if 'login' in login_result and login_result['login']['result'] == 'Success':
            log.info("Successfully logged in as %s", login_result['login']['lgusername'])
        else:
            raise LoginError(f"Login failed. Reason: '{login_result['login']['reason']}'")

        if 'warnings' in login_result:
            logging.warning("MediaWiki login warnings messages:")
            for message in login_result['warnings']:
                logging.warning(f"* {message}: {login_result['warnings'][message]['*']}")

        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)


class Clientlogin(_Login):
    @wbi_backoff()
    def __init__(self, user: str = None, password: str = None, mediawiki_api_url: str = None, token_renew_period: int = 1800, user_agent: str = None):
        """
        This class is used to log in with a user account

        :param user: The username
        :param password: The password
        :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param user_agent: UA string to use for API requests.
        """

        mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        session = Session()

        params_login = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login',
            'format': 'json'
        }

        # get login token
        login_token = session.post(mediawiki_api_url, data=params_login).json()['query']['tokens']['logintoken']

        params = {
            'action': 'clientlogin',
            'username': user,
            'password': password,
            'logintoken': login_token,
            'loginreturnurl': 'https://example.org/',
            'format': 'json'
        }

        login_result = session.post(mediawiki_api_url, data=params).json()

        log.debug(login_result)

        if 'clientlogin' in login_result:
            clientlogin = login_result['clientlogin']
            if clientlogin['status'] != 'PASS':
                log.debug(clientlogin)
                raise LoginError(f"Login failed ({clientlogin['messagecode']}). Message: '{clientlogin['message']}'")

            log.info("Successfully logged in as %s", clientlogin['username'])
        else:
            raise LoginError(f"Login failed ({login_result['error']['code']}). Message: '{login_result['error']['info']}'")

        if 'warnings' in login_result:
            logging.warning("MediaWiki login warnings messages:")
            for message in login_result['warnings']:
                logging.warning(f"* {message}: {login_result['warnings'][message]['*']}")

        super().__init__(session=session, token_renew_period=token_renew_period, user_agent=user_agent, mediawiki_api_url=mediawiki_api_url)


class LoginError(Exception):
    """Raised when there is an issue with the login"""
