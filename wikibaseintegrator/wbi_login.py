"""
Login class for Wikidata. Takes username and password and stores the session cookies and edit tokens.
"""
import logging
import time
import webbrowser
from typing import Optional

import requests
from mwoauth import ConsumerToken, Handshaker, OAuthException
from oauthlib.oauth2 import BackendApplicationClient, InvalidClientError
from requests import Session
from requests.cookies import RequestsCookieJar
from requests_oauthlib import OAuth1, OAuth2, OAuth2Session

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import get_user_agent

log = logging.getLogger(__name__)


class Login:
    """
    A class which handles the login to Wikidata and the generation of edit-tokens
    """

    @wbi_backoff()
    def __init__(self, auth_method: str = 'oauth2', user: str = None, password: str = None, mediawiki_api_url: str = None, mediawiki_index_url: str = None,
                 mediawiki_rest_url: str = None, token_renew_period: int = 1800, consumer_token: str = None, consumer_secret: str = None, access_token: str = None,
                 access_secret: str = None, callback_url: str = 'oob', user_agent: str = None):
        """
        This class handles several types of login procedures. Either use user and pwd authentication or OAuth.
        Wikidata clientlogin can also be used. If using one method, do NOT pass parameters for another method.
        :param user: the username which should be used for the login
        :param password: the password which should be used for the login
        :param token_renew_period: Seconds after which a new token should be requested from the Wikidata server
        :param consumer_token: The consumer key for OAuth
        :param consumer_secret: The consumer secret for OAuth
        :param access_token: The access token for OAuth
        :param access_secret: The access secret for OAuth
        :param callback_url: URL which should be used as the callback URL
        :param user_agent: UA string to use for API requests.
        """

        self.auth_method = auth_method
        self.consumer_token = consumer_token
        self.mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        self.mediawiki_index_url = str(mediawiki_index_url or config['MEDIAWIKI_INDEX_URL'])
        self.mediawiki_rest_url = str(mediawiki_rest_url or config['MEDIAWIKI_REST_URL'])
        self.token_renew_period = token_renew_period
        self.callback_url = callback_url
        self.user_agent = get_user_agent(user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None))

        if self.auth_method not in ['login', 'clientlogin', 'oauth1', 'oauth2']:
            raise ValueError("The auth_method must be 'login', 'clientlogin', 'oauth1' or 'oauth2'")

        self.session = requests.Session()
        self.edit_token: Optional[str] = None
        self.instantiation_time = time.time()
        self.response_qs: Optional[str] = None

        self.session.headers.update({
            'User-Agent': self.user_agent
        })

        if auth_method == 'oauth2':
            oauth = OAuth2Session(client=BackendApplicationClient(client_id=self.consumer_token))
            try:
                token = oauth.fetch_token(token_url=self.mediawiki_rest_url + '/oauth2/access_token', client_id=self.consumer_token, client_secret=consumer_secret)
            except InvalidClientError as err:
                raise LoginError(err) from err
            auth = OAuth2(token=token)
            self.session.auth = auth
            self.generate_edit_credentials()
        elif auth_method == 'oauth1':
            if access_token and access_secret:
                # OAuth procedure, based on https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers#Python
                auth = OAuth1(client_key=self.consumer_token, client_secret=consumer_secret, resource_owner_key=access_token, resource_owner_secret=access_secret)
                self.session.auth = auth
                self.generate_edit_credentials()
            else:
                # Oauth procedure, based on https://www.mediawiki.org/wiki/OAuth/For_Developers
                # Consruct a "consumer" from the key/secret provided by MediaWiki
                self.oauth1_consumer_token = ConsumerToken(self.consumer_token, consumer_secret)

                # Construct handshaker with wiki URI and consumer
                self.handshaker = Handshaker(mw_uri=self.mediawiki_index_url, consumer_token=self.oauth1_consumer_token, callback=self.callback_url, user_agent=self.user_agent)

                # Step 1: Initialize -- ask MediaWiki for a temp key/secret for user
                # redirect -> authorization -> callback url
                try:
                    self.redirect, self.request_token = self.handshaker.initiate(callback=self.callback_url)
                except OAuthException as err:
                    raise LoginError(err) from err
        elif auth_method in ('login', 'clientlogin'):
            params_login = {
                'action': 'query',
                'meta': 'tokens',
                'type': 'login',
                'format': 'json'
            }

            # get login token
            login_token = self.session.post(self.mediawiki_api_url, data=params_login).json()['query']['tokens']['logintoken']

            if auth_method == 'login':
                params = {
                    'action': 'login',
                    'lgname': user,
                    'lgpassword': password,
                    'lgtoken': login_token,
                    'format': 'json'
                }

                login_result = self.session.post(self.mediawiki_api_url, data=params).json()

                log.debug(login_result)

                if 'login' in login_result and login_result['login']['result'] == 'Success':
                    log.info("Successfully logged in as %s", login_result['login']['lgusername'])
                else:
                    raise LoginError(f"Login failed. Reason: '{login_result['login']['reason']}'")
            else:
                params = {
                    'action': 'clientlogin',
                    'username': user,
                    'password': password,
                    'logintoken': login_token,
                    'loginreturnurl': 'https://example.org/',
                    'format': 'json'
                }

                login_result = self.session.post(self.mediawiki_api_url, data=params).json()

                log.debug(login_result)

                if 'clientlogin' in login_result:
                    clientlogin = login_result['clientlogin']
                    if clientlogin['status'] != 'PASS':
                        raise LoginError(f"Login failed ({clientlogin['messagecode']}). Message: '{clientlogin['message']}'")

                    log.info("Successfully logged in as %s", clientlogin['username'])
                else:
                    raise LoginError(f"Login failed ({login_result['error']['code']}). Message: '{login_result['error']['info']}'")

            if 'warnings' in login_result:
                print("MediaWiki login warnings messages:")
                for message in login_result['warnings']:
                    print(f"* {message}: {login_result['warnings'][message]['*']}")

            self.generate_edit_credentials()

    def generate_edit_credentials(self) -> RequestsCookieJar:
        """
        request an edit token and update the cookie_jar in order to add the session cookie
        :return: Returns a json with all relevant cookies, aka cookie jar
        """
        params = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'csrf',
            'format': 'json'
        }
        response = self.session.get(self.mediawiki_api_url, params=params).json()
        if 'error' in response:
            raise LoginError(f"Login failed ({response['error']['code']}). Message: '{response['error']['info']}'")
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
        returns the requests session object used for the login.
        :return: Object of type requests.Session()
        """
        return self.session

    def continue_oauth(self, oauth_callback_data: str = None) -> None:
        """
        Continuation of OAuth procedure. Method must be explicitly called in order to complete OAuth. This allows
        external entities, e.g. websites, to provide tokens through callback URLs directly.
        :param oauth_callback_data: The callback URL received to a Web app
        :type oauth_callback_data: bytes
        :return:
        """
        self.response_qs = oauth_callback_data

        if not self.response_qs:
            webbrowser.open(self.redirect)
            self.response_qs = input("Callback URL: ")

        # input the url from redirect after authorization
        response_qs = self.response_qs.split('?')[-1]

        # Step 3: Complete -- obtain authorized key/secret for "resource owner"
        access_token = self.handshaker.complete(self.request_token, response_qs)

        if self.oauth1_consumer_token is None:
            raise ValueError("consumer_token can't be None")

        # input the access token to return a csrf (edit) token
        auth = OAuth1(client_key=self.oauth1_consumer_token.key, client_secret=self.oauth1_consumer_token.secret, resource_owner_key=access_token.key,
                      resource_owner_secret=access_token.secret)
        self.session.auth = auth
        self.generate_edit_credentials()


class LoginError(Exception):
    """Raised when there is an issue with the login"""
