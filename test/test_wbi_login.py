"""
Tests for the login flows (bot password, clientlogin, OAuth) against the
simulated MediaWiki API. Both the happy paths and the failure paths are
covered, without any real credentials or network access.
"""
import pytest

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_login import LoginError


@pytest.fixture
def credentials(wikibase):
    wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
    wikibase.valid_credentials['TestUser'] = 'password'
    return wikibase


class TestBotPasswordLogin:
    def test_successful_login(self, credentials):
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')

        assert login.get_edit_token() == credentials.csrf_token
        assert login.mediawiki_api_url == credentials.mediawiki_api_url

        # The login flow must be: login token request, login, csrf token request.
        actions = [request.get('action') or request.get('meta') for request in credentials.requests]
        assert actions == ['query', 'login', 'query']
        assert credentials.requests[1]['lgname'] == 'TestUser@bot'
        assert credentials.requests[1]['lgtoken'] == credentials.login_token

    def test_wrong_credentials(self, credentials):
        with pytest.raises(LoginError):
            wbi_login.Login(user='wrong', password='wrong')

    def test_edit_token_renewal(self, credentials):
        login = wbi_login.Login(user='TestUser@bot', password='botpassword', token_renew_period=0)
        first_token_requests = len(credentials.requests)

        # With a 0 renew period, asking for the token triggers a new csrf request.
        assert login.get_edit_token() == credentials.csrf_token
        assert len(credentials.requests) > first_token_requests

    def test_get_edit_cookie(self, credentials):
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        assert login.get_edit_cookie() is login.get_session().cookies


class TestClientLogin:
    def test_successful_login(self, credentials):
        login = wbi_login.Clientlogin(user='TestUser', password='password')
        assert login.get_edit_token() == credentials.csrf_token

    def test_wrong_credentials(self, credentials):
        with pytest.raises(LoginError):
            wbi_login.Clientlogin(user='wrong', password='wrong')


class TestAnonymousToken:
    def test_anonymous_csrf_token_is_rejected(self, credentials):
        # If the instance replies with the anonymous token '+\', login must fail.
        credentials.csrf_token = '+\\'
        with pytest.raises(LoginError):
            wbi_login.Login(user='TestUser@bot', password='botpassword')


class TestOAuth1:
    def test_owner_only_flow(self, credentials):
        # With access token/secret provided, the login goes straight to the csrf request.
        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret', access_token='access-token', access_secret='access-secret')
        assert login.get_edit_token() == credentials.csrf_token

    def test_csrf_error_raises_login_error(self, credentials):
        credentials.fail_next(code='mwoauth-invalid-authorization', info='The authorization headers in your request are not valid.')
        with pytest.raises(LoginError):
            wbi_login.OAuth1(consumer_token='wrong', consumer_secret='wrong', access_token='wrong', access_secret='wrong')


class TestOAuth2:
    def test_successful_flow(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_rest_url + '/oauth2/access_token', json={'access_token': 'oauth2-access-token', 'token_type': 'Bearer', 'expires_in': 14400})

        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        assert login.get_edit_token() == credentials.csrf_token

    def test_invalid_client(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_rest_url + '/oauth2/access_token', status_code=401, json={'error': 'invalid_client', 'error_description': 'Client authentication failed'})

        with pytest.raises(LoginError):
            wbi_login.OAuth2(consumer_token='wrong', consumer_secret='wrong')
