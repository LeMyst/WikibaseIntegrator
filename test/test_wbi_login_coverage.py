"""
Tests of the login paths not covered by test_wbi_login.py: the token renewal, the OAuth1 handshake errors and its
interactive continuation, the error and warning answers of login and clientlogin, the extra request parameters of the
login methods, and the cookie header of WCQSAuth. Everything runs against the simulated MediaWiki API or requests_mock,
the browser and the console input are replaced.
"""
import logging

import pytest
import requests

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_login import LoginError

CALLBACK_URL = 'https://example.org/callback?oauth_token=request-key&oauth_verifier=some-verifier'
REQUEST_TOKEN = 'oauth_token=request-key&oauth_token_secret=request-secret'
ACCESS_TOKEN = 'oauth_token=access-key&oauth_token_secret=access-secret'


@pytest.fixture
def credentials(wikibase):
    wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
    wikibase.valid_credentials['TestUser'] = 'password'
    return wikibase


def _actions(wikibase, start=0):
    return [request.get('action') or request.get('meta') for request in wikibase.requests[start:]]


def _authorization(request):
    """The OAuth1 Authorization header of a recorded request (requests-oauthlib sets it as bytes)."""
    header = request.headers['Authorization']
    return header.decode('ascii') if isinstance(header, bytes) else header


class TestTokenRenewal:
    def test_get_edit_cookie_renews_the_credentials_after_the_period(self, credentials):
        login = wbi_login.Login(user='TestUser@bot', password='botpassword', token_renew_period=0)
        requests_before = len(credentials.requests)
        time_before = login.instantiation_time

        assert login.get_edit_cookie() is login.get_session().cookies

        # A new CSRF token is requested, without a new login
        assert _actions(credentials, requests_before) == ['query']
        assert credentials.requests[-1]['type'] == 'csrf'
        assert login.instantiation_time >= time_before

    def test_get_edit_cookie_keeps_the_credentials_within_the_period(self, credentials):
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        requests_before = len(credentials.requests)

        login.get_edit_cookie()

        assert len(credentials.requests) == requests_before

    def test_default_reauthenticate_only_renews_the_csrf_token(self, credentials):
        # OAuth1 authenticates every request: reauthenticate() of _Login only requests a new CSRF token
        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret', access_token='access-token', access_secret='access-secret')
        requests_before = len(credentials.requests)
        login.edit_token = None
        login.instantiation_time = 0

        login.reauthenticate()

        assert _actions(credentials, requests_before) == ['query']
        assert login.edit_token == credentials.csrf_token
        assert login.instantiation_time > 0


class TestOAuth1Handshake:
    def test_initiate_error_raises_login_error(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_index_url, text='Error: mwoauth-consumer-not-approved')

        with pytest.raises(LoginError, match='^mwoauth-consumer-not-approved$'):
            wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')

    @pytest.mark.parametrize('content', ['', 'oauth_token=request-key', 'oauth_token_secret=request-secret', '<html>Not an OAuth answer</html>'])
    def test_initiate_without_token_raises_login_error(self, credentials, requests_mock, content):
        requests_mock.post(credentials.mediawiki_index_url, text=content)

        with pytest.raises(LoginError, match='MediaWiki response lacks token information'):
            wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')

    def test_initiate_records_the_request_token(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_index_url, text=REQUEST_TOKEN)

        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret', callback_url='https://example.org/callback')

        assert login.request_token_key == 'request-key'
        assert login.request_token_secret == 'request-secret'
        assert login.redirect == f'{credentials.mediawiki_index_url}?title=Special%3AOAuth%2Fauthenticate&oauth_token=request-key&oauth_consumer_key=consumer-token'
        # Only the initiate step was sent: the CSRF token is requested by continue_oauth()
        assert requests_mock.last_request.qs['title'] == ['special:oauth/initiate']
        assert 'oauth_callback="https%3A%2F%2Fexample.org%2Fcallback"' in _authorization(requests_mock.last_request)
        assert not credentials.requests

    def test_continue_oauth_asks_the_callback_url(self, credentials, requests_mock, monkeypatch):
        requests_mock.post(credentials.mediawiki_index_url, [{'text': REQUEST_TOKEN}, {'text': ACCESS_TOKEN}])
        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')
        opened = []
        prompts = []
        monkeypatch.setattr(wbi_login.webbrowser, 'open', opened.append)

        def fake_input(prompt):
            prompts.append(prompt)
            return CALLBACK_URL

        monkeypatch.setattr('builtins.input', fake_input)

        login.continue_oauth()

        # The authorization page is opened in the browser, then the callback URL is read from the console
        assert opened == [login.redirect]
        assert prompts == ['Callback URL: ']
        assert 'oauth_verifier="some-verifier"' in _authorization(requests_mock.request_history[1])
        assert login.get_edit_token() == credentials.csrf_token

    @pytest.mark.parametrize('callback', [
        'https://example.org/callback',
        'https://example.org/callback?oauth_token=request-key',
        'https://example.org/callback?oauth_verifier=some-verifier',
    ])
    def test_continue_oauth_without_token_raises_login_error(self, credentials, requests_mock, callback):
        requests_mock.post(credentials.mediawiki_index_url, text=REQUEST_TOKEN)
        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')

        with pytest.raises(LoginError, match='Query string lacks token information'):
            login.continue_oauth(callback)

        # The token step is not sent
        assert requests_mock.call_count == 1

    def test_continue_oauth_token_error_raises_login_error(self, credentials, requests_mock):
        requests_mock.post(credentials.mediawiki_index_url, [{'text': REQUEST_TOKEN}, {'text': 'Error: mwoauth-invalid-authorization'}])
        login = wbi_login.OAuth1(consumer_token='consumer-token', consumer_secret='consumer-secret')

        with pytest.raises(LoginError, match='^mwoauth-invalid-authorization$'):
            login.continue_oauth(CALLBACK_URL)

        assert not credentials.requests


class TestLoginAnswers:
    @pytest.mark.parametrize(('answer', 'message'), [
        ({'error': {'code': 'badtoken', 'info': 'Invalid token.'}}, "Unexpected API response: {'code': 'badtoken', 'info': 'Invalid token.'}"),
        ({'batchcomplete': ''}, "Unexpected API response: {'batchcomplete': ''}"),
    ])
    def test_login_unexpected_answer(self, credentials, monkeypatch, answer, message):
        monkeypatch.setattr(credentials, '_action_login', lambda params: answer)

        with pytest.raises(LoginError) as excinfo:
            wbi_login.Login(user='TestUser@bot', password='botpassword')

        assert str(excinfo.value) == f'Login failed. {message}'

    def test_login_failure_without_reason(self, credentials, monkeypatch):
        monkeypatch.setattr(credentials, '_action_login', lambda params: {'login': {'result': 'Aborted'}})

        with pytest.raises(LoginError, match="^Login failed. Reason: 'Aborted'$"):
            wbi_login.Login(user='TestUser@bot', password='botpassword')

    def test_login_warnings_are_logged(self, credentials, monkeypatch, caplog):
        answer = {
            'warnings': {'main': {'*': 'Subscribe to the mediawiki-api-announce mailing list.'}, 'login': {'*': 'Fetching a token via "action=login" is deprecated.'}},
            'login': {'result': 'Success', 'lgusername': 'TestUser@bot', 'lguserid': 1},
        }
        monkeypatch.setattr(credentials, '_action_login', lambda params: answer)

        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_login'):
            login = wbi_login.Login(user='TestUser@bot', password='botpassword')

        assert login.get_edit_token() == credentials.csrf_token
        assert [record.getMessage() for record in caplog.records] == [
            'MediaWiki login warnings messages:',
            '* main: Subscribe to the mediawiki-api-announce mailing list.',
            '* login: Fetching a token via "action=login" is deprecated.',
        ]

    def test_clientlogin_error_answer(self, credentials, monkeypatch):
        monkeypatch.setattr(credentials, '_action_clientlogin', lambda params: {'error': {'code': 'badtoken', 'info': 'Invalid CSRF token.'}})

        with pytest.raises(LoginError, match=r"^Login failed \(badtoken\). Message: 'Invalid CSRF token.'$"):
            wbi_login.Clientlogin(user='TestUser', password='password')

    def test_clientlogin_unexpected_answer(self, credentials, monkeypatch):
        monkeypatch.setattr(credentials, '_action_clientlogin', lambda params: {'batchcomplete': ''})

        with pytest.raises(LoginError, match=r"^Login failed. Unexpected API response: \{'batchcomplete': ''\}$"):
            wbi_login.Clientlogin(user='TestUser', password='password')

    def test_clientlogin_failure_message(self, credentials):
        with pytest.raises(LoginError, match=r"^Login failed \(wrongpassword\). Message: 'Incorrect username or password entered. Please try again.'$"):
            wbi_login.Clientlogin(user='TestUser', password='wrong')

    def test_clientlogin_warnings_are_logged(self, credentials, monkeypatch, caplog):
        answer = {'warnings': {'main': {'*': 'Unrecognized parameter: foo.'}}, 'clientlogin': {'status': 'PASS', 'username': 'TestUser'}}
        monkeypatch.setattr(credentials, '_action_clientlogin', lambda params: answer)

        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_login'):
            login = wbi_login.Clientlogin(user='TestUser', password='password')

        assert login.get_edit_token() == credentials.csrf_token
        assert [record.getMessage() for record in caplog.records] == ['MediaWiki login warnings messages:', '* main: Unrecognized parameter: foo.']


@pytest.mark.parametrize(('login_class', 'user', 'password', 'action'), [
    (wbi_login.Login, 'TestUser@bot', 'botpassword', 'login'),
    (wbi_login.Clientlogin, 'TestUser', 'password', 'clientlogin'),
])
class TestLoginRequestParameters:
    def test_unsupported_kwargs_are_ignored(self, credentials, caplog, login_class, user, password, action):
        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_login'):
            login = login_class(user=user, password=password, unknown_parameter='value')

        assert login.get_edit_token() == credentials.csrf_token
        assert [record.getMessage() for record in caplog.records] == ["Unsupported kwargs were ignored: {'unknown_parameter'}"]
        assert _actions(credentials) == ['query', action, 'query']

    def test_supported_kwargs_are_passed_to_the_login_requests(self, credentials, requests_mock, login_class, user, password, action):
        login = login_class(user=user, password=password, timeout=12, verify=False)

        assert login.get_edit_token() == credentials.csrf_token
        login_requests = requests_mock.request_history[:2]
        assert [request.method for request in login_requests] == ['POST', 'POST']
        assert all(request.timeout == 12 and request.verify is False for request in login_requests)

    def test_headers_are_added_to_the_login_requests(self, credentials, requests_mock, login_class, user, password, action):
        # Passing headers used to raise "TypeError: got multiple values for keyword argument 'headers'"
        login = login_class(user=user, password=password, headers={'X-Test': 'value'}, user_agent='TestAgent/1.0 (test@example.org)')

        assert login.get_edit_token() == credentials.csrf_token
        assert _actions(credentials) == ['query', action, 'query']
        for request in requests_mock.request_history[:2]:
            assert request.headers['X-Test'] == 'value'
            assert request.headers['User-Agent'].startswith('TestAgent/1.0 (test@example.org)')

    def test_reauthenticate_reuses_the_kwargs(self, credentials, requests_mock, login_class, user, password, action):
        login = login_class(user=user, password=password, headers={'X-Test': 'value'})
        history_before = len(requests_mock.request_history)

        login.reauthenticate()

        assert _actions(credentials)[-3:] == ['query', action, 'query']
        assert [request.headers.get('X-Test') for request in requests_mock.request_history[history_before:]] == ['value', 'value', None]


class TestWCQSAuthCookieHeader:
    def test_bytes_cookie_header_is_decoded(self):
        request = requests.Request('POST', 'https://commons-query.wikimedia.org/sparql').prepare()
        request.headers['Cookie'] = b'wcqsSession=jwt123'

        wbi_login.WCQSAuth('good.cookie')(request)

        assert request.headers['Cookie'] == 'wcqsSession=jwt123; wcqsOauth=good.cookie'

    def test_cookie_header_is_created(self):
        request = requests.Request('POST', 'https://commons-query.wikimedia.org/sparql').prepare()

        wbi_login.WCQSAuth('good.cookie')(request)

        assert request.headers['Cookie'] == 'wcqsOauth=good.cookie'

    def test_redirect_is_not_checked(self):
        # The redirect setting the wcqsSession cookie is an HTML page too, it must not raise
        response = requests.Response()
        response.status_code = 307
        response.headers['Location'] = '/sparql'
        response.headers['Content-Type'] = 'text/html; charset=UTF-8'

        assert wbi_login.WCQSAuth._check_response(response) is response
