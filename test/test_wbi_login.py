"""
Tests for the login flows (bot password, clientlogin, OAuth) against the
simulated MediaWiki API. Both the happy paths and the failure paths are
covered, without any real credentials or network access.
"""
import pytest

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_helpers import edit_entity
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

    def test_reauthenticate_redoes_full_login(self, credentials):
        # generate_edit_credentials() alone can't recover a session the server already dropped (#902):
        # reauthenticate() must redo the login-token + login round trip, not just fetch a new csrf token.
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        requests_before = len(credentials.requests)

        login.reauthenticate()

        actions = [request.get('action') or request.get('meta') for request in credentials.requests[requests_before:]]
        assert actions == ['query', 'login', 'query']
        assert login.get_edit_token() == credentials.csrf_token

    def test_session_loss_is_recovered_on_write(self, credentials):
        # Simulate the server having invalidated the session mid-run: the very next write must
        # transparently re-login and retry instead of raising MWApiError.
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        credentials.fail_next(code='assertbotfailed', info='You do not have the "bot" right, so the action could not be completed.')

        result = edit_entity(data={}, id='Q1', login=login, is_bot=True)

        assert result['success'] == 1
        assert login.get_edit_token() == credentials.csrf_token


class TestClientLogin:
    def test_successful_login(self, credentials):
        login = wbi_login.Clientlogin(user='TestUser', password='password')
        assert login.get_edit_token() == credentials.csrf_token

    def test_wrong_credentials(self, credentials):
        with pytest.raises(LoginError):
            wbi_login.Clientlogin(user='wrong', password='wrong')

    def test_reauthenticate_redoes_full_login(self, credentials):
        login = wbi_login.Clientlogin(user='TestUser', password='password')
        requests_before = len(credentials.requests)

        login.reauthenticate()

        actions = [request.get('action') or request.get('meta') for request in credentials.requests[requests_before:]]
        assert actions == ['query', 'clientlogin', 'query']
        assert login.get_edit_token() == credentials.csrf_token

    def test_session_loss_is_recovered_on_write(self, credentials):
        login = wbi_login.Clientlogin(user='TestUser', password='password')
        credentials.fail_next(code='assertuserfailed', info='You are no longer logged in, so the action could not be completed.')

        result = edit_entity(data={}, id='Q1', login=login)

        assert result['success'] == 1
        assert login.get_edit_token() == credentials.csrf_token


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

    def test_three_legged_flow(self, credentials, requests_mock):
        # Step 1 (initiate) and step 3 (token) both post to Special:OAuth on the index endpoint.
        requests_mock.post(credentials.mediawiki_index_url, [
            {'text': 'oauth_token=request-key&oauth_token_secret=request-secret'},
            {'text': 'oauth_token=access-key&oauth_token_secret=access-secret'},
        ])

        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')
        assert 'oauth_token=request-key' in login.redirect
        assert login.request_token_key == 'request-key'

        login.continue_oauth('https://example.org/callback?oauth_token=request-key&oauth_verifier=some-verifier')
        assert login.get_edit_token() == credentials.csrf_token

    def test_three_legged_flow_wrong_request_token(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_index_url, text='oauth_token=request-key&oauth_token_secret=request-secret')

        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')
        with pytest.raises(LoginError):
            login.continue_oauth('https://example.org/callback?oauth_token=unexpected-key&oauth_verifier=some-verifier')


class TestOAuth2:
    def test_successful_flow(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_rest_url + '/oauth2/access_token', json={'access_token': 'oauth2-access-token', 'token_type': 'Bearer', 'expires_in': 14400})

        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        assert login.get_edit_token() == credentials.csrf_token

    def test_invalid_client(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_rest_url + '/oauth2/access_token', status_code=401, json={'error': 'invalid_client', 'error_description': 'Client authentication failed'})

        with pytest.raises(LoginError):
            wbi_login.OAuth2(consumer_token='wrong', consumer_secret='wrong')

    def test_access_token_is_refreshed_on_renewal(self, credentials, requests_mock):
        token_matcher = requests_mock.post(credentials.mediawiki_rest_url + '/oauth2/access_token',
                                           json={'access_token': 'oauth2-access-token', 'token_type': 'Bearer', 'expires_in': 14400})

        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret', token_renew_period=0)
        calls_after_init = token_matcher.call_count

        # The short-lived access token has no refresh token, so renewing the credentials must re-fetch it (not only the CSRF token).
        login.get_edit_token()
        assert token_matcher.call_count > calls_after_init
