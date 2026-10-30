"""
Tests for wbi_helpers: low-level API call machinery (retries, maxlag, error
mapping), search, merge, SPARQL and the various pure helper functions.
"""
import copy
import inspect
import logging
import threading
import uuid
from types import MappingProxyType
from urllib.parse import quote_plus

import pytest
import requests
import ujson

from wikibaseintegrator import WikibaseIntegrator, wbi_helpers
from wikibaseintegrator.datatypes import Item, MonolingualText, Quantity, String, Time
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseSnakType
from wikibaseintegrator.wbi_exceptions import (AnonymousEditNotAllowedError, EmptyValueError, MaxRetriesReachedException, MissingEntityException, MissingExtensionError,
                                               ModificationFailed, MWApiError, NonExistentEntityError, SaveFailed)
from wikibaseintegrator.wbi_helpers import (check_constraints, check_wikibase, create_redirect, download_entity_ttl, edit_entity, execute_sparql_query, format2wbi, format_amount,
                                            fulltext_search, generate_entity_instances, get_available_badges, get_user_agent, lexeme_add_form, lexeme_edit_sense,
                                            lexeme_remove_form, lexeme_remove_sense, mediawiki_api_call, mediawiki_api_call_helper, merge_items, merge_multiple_items, parse_value,
                                            remove_claims, search_entities, set_claim)


class FakeLogin:
    """Minimal stand-in for wbi_login._Login, without any HTTP interaction."""

    def __init__(self, mediawiki_api_url, edit_token='fakelogintoken+\\'):
        self.mediawiki_api_url = mediawiki_api_url
        self.edit_token = edit_token
        self.session = requests.Session()
        self.reauthenticate_calls = 0

    def get_edit_token(self):
        return self.edit_token

    def get_session(self):
        return self.session

    def reauthenticate(self):
        self.reauthenticate_calls += 1
        self.edit_token = 'renewed-token+\\'


class TestRetryBehaviour:
    """Behaviour of mediawiki_api_call when the instance is unhealthy."""

    def test_retry_on_server_errors_until_success(self, wikibase, requests_mock):
        url = 'https://unstable.example.org/w/api.php'
        requests_mock.post(url, [
            {'status_code': 503, 'text': 'Service Unavailable'},
            {'status_code': 502, 'text': 'Bad Gateway'},
            {'json': {'success': 1}, 'status_code': 200},
        ])

        result = mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=5, retry_after=1)
        assert result == {'success': 1}
        assert requests_mock.call_count == 3

    @pytest.mark.parametrize('status_code', [500, 502, 503, 504])
    def test_max_retries_reached_on_persistent_server_error(self, requests_mock, status_code):
        url = 'https://unstable.example.org/w/api.php'
        requests_mock.post(url, status_code=status_code, text='error')

        with pytest.raises(MaxRetriesReachedException):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'}, mediawiki_api_url=url, max_retries=2, retry_after=1, allow_anonymous=True)

    def test_max_retries_reached_on_connection_error(self, requests_mock):
        url = 'https://unreachable.example.org/w/api.php'
        requests_mock.post(url, exc=requests.exceptions.ConnectionError)

        with pytest.raises(MaxRetriesReachedException):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'}, mediawiki_api_url=url, max_retries=2, retry_after=1, allow_anonymous=True)

    def test_client_error_is_not_retried(self, requests_mock):
        url = 'https://broken.example.org/w/api.php'
        requests_mock.post(url, status_code=400, text='Bad Request')

        with pytest.raises(requests.HTTPError):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'}, mediawiki_api_url=url, max_retries=2, retry_after=1, allow_anonymous=True)

        assert requests_mock.call_count == 1

    def test_maxlag_is_retried_then_succeeds(self, requests_mock):
        url = 'https://lagging.example.org/w/api.php'
        requests_mock.post(url, [
            {'json': {'error': {'code': 'maxlag', 'info': 'Waiting for a database server', 'lag': 3}}},
            {'json': {'entities': {}, 'success': 1}},
        ])

        result = mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'}, mediawiki_api_url=url, max_retries=3, retry_after=1,
                                           allow_anonymous=True)
        assert result['success'] == 1
        assert requests_mock.call_count == 2

    @pytest.fixture
    def slept(self, monkeypatch):
        """The waits between the tries."""
        waits: list[float] = []
        monkeypatch.setattr('wikibaseintegrator.wbi_helpers.sleep', waits.append)
        return waits

    def test_failure_waits_double_up_to_retry_after(self, requests_mock, slept):
        url = 'https://unstable.example.org/w/api.php'
        requests_mock.post(url, [{'status_code': 503, 'text': 'Service Unavailable'}] * 4 + [{'json': {'success': 1}, 'status_code': 200}])

        assert mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=10, retry_after=3) == {'success': 1}
        # Instead of retry_after (60 s by default) after each failure
        assert slept == [1, 2, 3, 3]

    def test_failures_are_limited_by_backoff_max_tries(self, requests_mock, slept):
        url = 'https://unreachable.example.org/w/api.php'
        requests_mock.post(url, exc=requests.exceptions.ConnectionError('unreachable'))
        wbi_config['BACKOFF_MAX_TRIES'] = 3

        with pytest.raises(MaxRetriesReachedException) as excinfo:
            mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=20, retry_after=60)

        # max_retries (20) is for the instance asking to slow down, a failure is tried BACKOFF_MAX_TRIES times
        assert requests_mock.call_count == 3
        assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
        # No wait after the last try
        assert slept == [1, 2]

    def test_maxlag_is_not_limited_by_backoff_max_tries(self, requests_mock, slept):
        url = 'https://lagging.example.org/w/api.php'
        maxlag = {'json': {'error': {'code': 'maxlag', 'info': 'Waiting for a database server', 'lag': 3}}}
        requests_mock.post(url, [maxlag] * 4 + [{'json': {'success': 1}}])
        wbi_config['BACKOFF_MAX_TRIES'] = 2

        assert mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=10, retry_after=60) == {'success': 1}
        assert requests_mock.call_count == 5

    def test_max_retries_without_wait_after_the_last_try(self, requests_mock, slept):
        url = 'https://lagging.example.org/w/api.php'
        requests_mock.post(url, json={'error': {'code': 'maxlag', 'info': 'Waiting for a database server', 'lag': 3}})

        with pytest.raises(MaxRetriesReachedException):
            mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=3, retry_after=60)

        assert requests_mock.call_count == 3 and len(slept) == 2

    def test_http_429_is_retried_after_the_delay_asked(self, requests_mock, slept):
        url = 'https://throttled.example.org/w/api.php'
        requests_mock.post(url, [{'status_code': 429, 'headers': {'Retry-After': '7'}, 'text': 'Too Many Requests'}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=3, retry_after=60) == {'success': 1}
        assert slept == [7]

    def test_retry_after_is_capped_by_backoff_max_value(self, requests_mock, slept):
        url = 'https://throttled.example.org/w/api.php'
        requests_mock.post(url, [{'status_code': 429, 'headers': {'Retry-After': '100000'}, 'text': 'Too Many Requests'}, {'json': {'success': 1}}])
        wbi_config['BACKOFF_MAX_VALUE'] = 60

        mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=3, retry_after=5)
        assert slept == [60]

    @pytest.mark.parametrize('retry_after_header', ['Wed, 21 Oct 2015 07:28:00 GMT', '-5', 'nan', ''])
    def test_rate_limit_with_an_unusable_retry_after(self, requests_mock, slept, retry_after_header):
        # int() of an HTTP date used to raise a ValueError
        url = 'https://throttled.example.org/w/api.php'
        throttled = {'error': {'code': 'ratelimited', 'info': 'Rate limited', 'messages': [{'name': 'actionthrottledtext'}]}}
        requests_mock.post(url, [{'json': throttled, 'headers': {'Retry-After': retry_after_header}}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=3, retry_after=4) == {'success': 1}
        assert slept == [4]

    def test_readonly_is_waited_for(self, requests_mock, slept):
        url = 'https://maintenance.example.org/w/api.php'
        readonly = {'error': {'code': 'readonly', 'info': 'The wiki is currently in read-only mode.'}}
        requests_mock.post(url, [{'json': readonly}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=3, retry_after=9) == {'success': 1}
        assert slept == [9]

    def test_read_timeout_of_a_read_is_retried(self, requests_mock, slept):
        url = 'https://slow.example.org/w/api.php'
        requests_mock.post(url, [{'exc': requests.exceptions.ReadTimeout('read timed out')}, {'json': {'entities': {}, 'success': 1}}])

        result = mediawiki_api_call('POST', mediawiki_api_url=url, data={'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=5, retry_after=60)

        assert result['success'] == 1 and slept == [1]

    def test_read_timeout_of_a_write_is_not_retried(self, requests_mock, slept):
        # The edit may have been saved before the timeout: trying again could save it twice
        url = 'https://slow.example.org/w/api.php'
        requests_mock.post(url, exc=requests.exceptions.ReadTimeout('read timed out'))

        with pytest.raises(requests.exceptions.ReadTimeout):
            mediawiki_api_call('POST', mediawiki_api_url=url, data={'action': 'wbeditentity', 'id': 'Q42', 'data': '{}'}, max_retries=5, retry_after=60)

        assert requests_mock.call_count == 1 and slept == []

    def test_read_timeouts_of_a_read_are_limited_by_backoff_max_tries(self, requests_mock, slept):
        url = 'https://slow.example.org/w/api.php'
        requests_mock.post(url, exc=requests.exceptions.ReadTimeout('read timed out'))
        wbi_config['BACKOFF_MAX_TRIES'] = 2

        with pytest.raises(MaxRetriesReachedException) as excinfo:
            mediawiki_api_call('POST', mediawiki_api_url=url, data={'action': 'query', 'meta': 'siteinfo'}, max_retries=20, retry_after=60)

        assert requests_mock.call_count == 2 and isinstance(excinfo.value.__cause__, requests.exceptions.ReadTimeout)

    def test_failure_waits_are_capped_by_backoff_max_value(self, requests_mock, slept):
        url = 'https://unstable.example.org/w/api.php'
        requests_mock.post(url, [{'status_code': 503, 'text': 'Service Unavailable'}] * 3 + [{'json': {'success': 1}, 'status_code': 200}])
        wbi_config['BACKOFF_MAX_VALUE'] = 2

        mediawiki_api_call('POST', mediawiki_api_url=url, max_retries=10, retry_after=60)
        assert slept == [1, 2, 2]

    def test_default_max_retries(self):
        assert inspect.signature(mediawiki_api_call).parameters['max_retries'].default == 20
        assert inspect.signature(mediawiki_api_call_helper).parameters['max_retries'].default == 20

    def test_format_must_be_json(self):
        with pytest.raises(ValueError):
            mediawiki_api_call('POST', mediawiki_api_url='https://example.org/w/api.php', data={'format': 'xml'})


class TestDefaultSession:
    """Requests made without a Login share a session per thread, never across threads."""

    def test_session_is_reused_within_a_thread(self):
        assert wbi_helpers._get_default_session() is wbi_helpers._get_default_session()

    def test_session_is_not_shared_across_threads(self):
        sessions = []
        thread = threading.Thread(target=lambda: sessions.append(wbi_helpers._get_default_session()))
        thread.start()
        thread.join()

        assert sessions[0] is not wbi_helpers._get_default_session()

    def test_anonymous_call_uses_default_session(self, requests_mock, monkeypatch):
        url = 'https://example.org/w/api.php'
        requests_mock.post(url, json={'success': 1})
        session = requests.Session()
        monkeypatch.setattr(wbi_helpers, '_get_default_session', lambda: session)
        sent = []
        monkeypatch.setattr(session, 'request', lambda **kwargs: sent.append(kwargs) or requests.Session.request(session, **kwargs))

        mediawiki_api_call('POST', mediawiki_api_url=url, data={'action': 'query'})
        assert len(sent) == 1

    @pytest.mark.parametrize('name', ['default_session', 'helpers_session'])
    def test_former_module_sessions_are_deprecated(self, name):
        with pytest.warns(DeprecationWarning):
            assert getattr(wbi_helpers, name) is wbi_helpers._get_default_session()

    def test_unknown_attribute_still_raises(self):
        with pytest.raises(AttributeError):
            getattr(wbi_helpers, 'does_not_exist')


class TestTimeout:
    def test_default_timeout_is_applied(self, wikibase, requests_mock):
        wbi_config['TIMEOUT'] = (3, 33)
        mediawiki_api_call('POST', mediawiki_api_url=wikibase.mediawiki_api_url, data={'action': 'wbsearchentities', 'search': 'x', 'language': 'en', 'format': 'json'})
        assert requests_mock.last_request.timeout == (3, 33)

    def test_explicit_timeout_is_not_overridden(self, wikibase, requests_mock):
        wbi_config['TIMEOUT'] = (3, 33)
        mediawiki_api_call('POST', mediawiki_api_url=wikibase.mediawiki_api_url, data={'action': 'wbsearchentities', 'search': 'x', 'language': 'en', 'format': 'json'}, timeout=7)
        assert requests_mock.last_request.timeout == 7


class TestAnonymousEdit:
    def test_anonymous_edit_not_allowed_raises_dedicated_error(self, wikibase):
        # A login object that only yields the anonymous token must trigger the dedicated exception, not a bare Exception.
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url, edit_token='+\\')
        with pytest.raises(AnonymousEditNotAllowedError):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, login=login, mediawiki_api_url=wikibase.mediawiki_api_url)


class TestErrorMapping:
    """MediaWiki error payloads must be converted to the right exceptions."""

    def test_no_such_entity(self, wikibase):
        wikibase.fail_next(code='no-such-entity', info='Could not find an entity with the ID "Q1".')
        with pytest.raises(NonExistentEntityError):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q1', 'format': 'json'}, allow_anonymous=True)

    def test_missing_title(self, wikibase):
        wikibase.fail_next(code='missingtitle', info='The page you specified does not exist.')
        with pytest.raises(NonExistentEntityError):
            mediawiki_api_call_helper(data={'action': 'delete', 'title': 'Q1', 'format': 'json'}, allow_anonymous=True)

    def test_modification_failed(self, wikibase):
        wikibase.fail_next(code='modification-failed', info='Conflict detected.', messages=[{'name': 'wikibase-validator-label-conflict'}])
        with pytest.raises(ModificationFailed):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, allow_anonymous=True)

    def test_sitelink_conflict(self, wikibase):
        wikibase.fail_next(code='failed-save', info='The save has failed.', messages=[{'name': 'wikibase-validator-sitelink-conflict'}])
        with pytest.raises(SaveFailed):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, allow_anonymous=True)

    def test_generic_error(self, wikibase):
        wikibase.fail_next(code='badtoken', info='Invalid CSRF token.')
        with pytest.raises(MWApiError):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, allow_anonymous=True)


class TestMissingLexemeExtension:
    """Lexeme requests sent to a Wikibase instance without WikibaseLexeme must raise a clear error (#500)."""

    # Payloads returned by Wikimedia Commons, a Wikibase instance without lexeme support
    UNKNOWN_ACTION = {'code': 'badvalue', 'info': 'Unrecognized value for parameter "action": wbladdform.'}
    UNKNOWN_NEW = {'code': 'badvalue', 'info': 'Unrecognized value for parameter "new": lexeme.'}

    @staticmethod
    def _actions(wikibase):
        return [request.get('action') for request in wikibase.requests]

    def test_get_lexeme_without_lexeme_support(self, wikibase):
        wikibase.entity_types = ['item', 'property']

        with pytest.raises(MissingExtensionError) as excinfo:
            WikibaseIntegrator().lexeme.get('L5')

        assert excinfo.value.extension == 'WikibaseLexeme'
        assert 'WikibaseLexeme' in str(excinfo.value)
        assert 'Could not find an entity with the ID "L5".' in str(excinfo.value)
        # Still a NonExistentEntityError, for the code already catching it
        assert isinstance(excinfo.value, NonExistentEntityError)
        assert self._actions(wikibase) == ['wbgetentities', 'paraminfo']

    @pytest.mark.parametrize('entity_id', ['L5-F1', 'L5-S1', 'wd:L5'])
    def test_get_form_sense_or_federated_lexeme_without_lexeme_support(self, wikibase, entity_id):
        wikibase.entity_types = ['item', 'property']

        with pytest.raises(MissingExtensionError):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': entity_id, 'format': 'json'}, allow_anonymous=True)

    def test_missing_lexeme_with_lexeme_support(self, wikibase):
        """The instance supports lexemes: the lexeme is really missing."""
        with pytest.raises(NonExistentEntityError) as excinfo:
            WikibaseIntegrator().lexeme.get('L5')

        assert not isinstance(excinfo.value, MissingExtensionError)

    def test_missing_item_does_not_check_lexeme_support(self, wikibase):
        wikibase.entity_types = ['item', 'property']

        with pytest.raises(NonExistentEntityError) as excinfo:
            WikibaseIntegrator().item.get('Q5')

        assert not isinstance(excinfo.value, MissingExtensionError)
        assert 'paraminfo' not in self._actions(wikibase)

    def test_unknown_lexeme_action(self, wikibase):
        wikibase.fail_next(**self.UNKNOWN_ACTION)

        with pytest.raises(MissingExtensionError) as excinfo:
            lexeme_add_form('L5', data={}, allow_anonymous=True)

        assert excinfo.value.code == 'badvalue'
        assert 'paraminfo' not in self._actions(wikibase)

    def test_unknown_lexeme_action_before_mediawiki_1_35(self, wikibase):
        wikibase.fail_next(code='unknown_action', info='Unrecognized value for parameter "action": wbladdform.')

        with pytest.raises(MissingExtensionError):
            lexeme_add_form('L5', data={}, allow_anonymous=True)

    def test_new_lexeme_without_lexeme_support(self, wikibase):
        wikibase.fail_next(**self.UNKNOWN_NEW)

        with pytest.raises(MissingExtensionError):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'new': 'lexeme', 'data': '{}', 'format': 'json'}, allow_anonymous=True)

    def test_unrelated_bad_value(self, wikibase):
        wikibase.fail_next(code='badvalue', info='Unrecognized value for parameter "props": foo.')

        with pytest.raises(MWApiError) as excinfo:
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'L5', 'props': 'foo', 'format': 'json'}, allow_anonymous=True)

        assert not isinstance(excinfo.value, MissingExtensionError)

    def test_failed_check_keeps_the_original_error(self, wikibase):
        """The lexeme support can't be checked: the original error is raised."""
        wikibase.fail_next(code='no-such-entity', info='Could not find an entity with the ID "L5".', id='L5')
        wikibase.fail_next(code='internal_api_error_DBQueryError', info='A database query error has occurred.')

        with pytest.raises(NonExistentEntityError) as excinfo:
            WikibaseIntegrator().lexeme.get('L5')

        assert not isinstance(excinfo.value, MissingExtensionError)


@pytest.mark.parametrize('error_code', ['assertuserfailed', 'assertbotfailed', 'notloggedin'])
class TestSessionRecovery:
    """
    A CSRF token can look fresh yet the server has already dropped the underlying session (#902).
    On assertuserfailed/assertbotfailed/notloggedin, the login object must be asked to fully
    re-authenticate and the call retried, instead of failing outright.
    """

    def test_session_loss_triggers_reauthentication_and_retry(self, wikibase, error_code):
        wikibase.fail_next(code=error_code, info='You are no longer logged in, so the action could not be completed.')
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        result = mediawiki_api_call_helper(data={'action': 'query', 'format': 'json'}, login=login, mediawiki_api_url=wikibase.mediawiki_api_url)

        assert result == {'batchcomplete': ''}
        assert login.reauthenticate_calls == 1
        # The retried request must carry the token obtained after re-authenticating, not the stale one.
        assert wikibase.last_request['token'] == 'renewed-token+\\'

    def test_session_loss_without_login_is_not_retried(self, wikibase, error_code):
        # Without a login object there is nothing to re-authenticate with, so the error must surface as-is.
        wikibase.fail_next(code=error_code, info='You are no longer logged in, so the action could not be completed.')
        with pytest.raises(MWApiError):
            mediawiki_api_call_helper(data={'action': 'query', 'format': 'json'}, allow_anonymous=True)

    def test_error_persisting_after_reauthentication_is_raised(self, wikibase, error_code):
        # The same error right after a fresh login doesn't come from a lost session (e.g. assertbotfailed for an
        # account without the bot right): it must be raised instead of logging in again on every retry.
        for _ in range(3):
            wikibase.fail_next(code=error_code, info='You do not have the "bot" right, so the action could not be completed.')
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        with pytest.raises(MWApiError) as excinfo:
            mediawiki_api_call_helper(data={'action': 'query', 'format': 'json'}, login=login, is_bot=True)

        assert excinfo.value.code == error_code
        assert login.reauthenticate_calls == 1


class TestAuthenticationGuards:
    def test_anonymous_must_be_explicit(self, wikibase):
        # allow_anonymous=False without login object
        with pytest.raises(ValueError):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'})

    def test_anonymous_query_allowed(self, wikibase, item_q582):
        assert mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}, allow_anonymous=True)

    def test_mismatched_api_url_with_login(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        with pytest.raises(ValueError):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'format': 'json'}, login=login, mediawiki_api_url='https://an-other-instance.example.org/w/api.php')

    def test_anonymous_token_with_login_refused(self, wikibase):
        # A login object returning an anonymous token must be rejected before any HTTP call.
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url, edit_token='+\\')
        with pytest.raises(Exception, match='Anonymous edit are not allowed'):
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'format': 'json'}, login=login)

    def test_assert_user_and_bot_flags(self, wikibase, item_q582):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}, login=login)
        assert wikibase.last_request['assert'] == 'user'
        assert wikibase.last_request['token'] == login.edit_token

        mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}, login=login, is_bot=True)
        assert wikibase.last_request['assert'] == 'bot'


class TestRequestDataNotMutated:
    """The caller's request payload must be left untouched by the API helpers."""

    def test_helper_does_not_mutate_caller_data(self, wikibase, item_q582):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        data = {'action': 'wbgetentities', 'ids': 'Q582'}

        mediawiki_api_call_helper(data=data, login=login, is_bot=True)

        assert data == {'action': 'wbgetentities', 'ids': 'Q582'}
        # The copy sent over the wire still gets the automatic parameters
        assert wikibase.last_request['token'] == login.edit_token
        assert wikibase.last_request['assert'] == 'bot'
        assert wikibase.last_request['maxlag'] == '5'
        assert wikibase.last_request['format'] == 'json'

    def test_api_call_does_not_mutate_caller_data(self, requests_mock):
        url = 'https://example.org/w/api.php'
        requests_mock.post(url, json={'success': 1})
        data = {'action': 'query'}

        mediawiki_api_call('POST', mediawiki_api_url=url, data=data)

        assert data == {'action': 'query'}
        assert 'format=json' in requests_mock.last_request.text

    def test_api_call_accepts_read_only_mapping(self, requests_mock):
        url = 'https://example.org/w/api.php'
        requests_mock.post(url, json={'success': 1})

        assert mediawiki_api_call('POST', mediawiki_api_url=url, data=MappingProxyType({'action': 'query'})) == {'success': 1}
        assert 'format=json' in requests_mock.last_request.text

    def test_helper_accepts_none_data(self, requests_mock):
        url = 'https://example.org/w/api.php'
        requests_mock.post(url, json={'success': 1})

        assert mediawiki_api_call_helper(data=None, mediawiki_api_url=url, allow_anonymous=True) == {'success': 1}


class TestUserAgent:
    def test_no_warning_when_user_agent_set(self, wikibase, item_q582, caplog):
        data = {'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}
        with caplog.at_level(logging.WARNING):
            mediawiki_api_call_helper(data=data, allow_anonymous=True, user_agent='MyWikibaseBot/0.5')
        assert 'Please set an user agent' not in caplog.text

    def test_warning_on_wikimedia_instance_without_user_agent(self, requests_mock, caplog):
        # The warning only triggers for Wikimedia Foundation instances.
        requests_mock.post('https://www.wikidata.org/w/api.php', json={'entities': {}, 'success': 1})
        wbi_config['USER_AGENT'] = None

        with caplog.at_level(logging.WARNING):
            mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q42', 'format': 'json'}, mediawiki_api_url='https://www.wikidata.org/w/api.php',
                                      allow_anonymous=True)
        assert 'Please set an user agent' in caplog.text

    def test_user_agent_sent_in_headers(self, wikibase, item_q582, requests_mock):
        mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}, allow_anonymous=True, user_agent='MyWikibaseBot/0.5')
        sent_user_agent = requests_mock.last_request.headers['User-Agent']
        assert sent_user_agent.startswith('MyWikibaseBot/0.5')
        assert 'WikibaseIntegrator' in sent_user_agent

    def test_get_user_agent(self):
        new_user_agent = get_user_agent(user_agent='MyWikibaseBot/0.5')
        assert new_user_agent.startswith('MyWikibaseBot/0.5')
        assert 'WikibaseIntegrator' in new_user_agent

        assert get_user_agent(user_agent=None).startswith('WikibaseIntegrator/')


class TestSearchEntities:
    def test_search_with_continuation(self, wikibase):
        wikibase.search_results = [{'id': f'Q{i}', 'label': f'result {i}', 'match': {'type': 'label', 'text': f'result {i}'}} for i in range(60)]

        results = search_entities('rivaroxaban', max_results=100)
        assert len(results) == 60
        assert results[0] == 'Q0'

        # Two API calls: one initial, one for the continuation
        search_requests = [r for r in wikibase.requests if r.get('action') == 'wbsearchentities']
        assert len(search_requests) == 2
        assert search_requests[1]['continue'] == '50'

    def test_search_stops_at_max_results(self, wikibase):
        wikibase.search_results = [{'id': f'Q{i}', 'label': f'result {i}', 'match': {}} for i in range(60)]

        results = search_entities('rivaroxaban', max_results=50)
        assert len(results) == 50
        search_requests = [r for r in wikibase.requests if r.get('action') == 'wbsearchentities']
        assert len(search_requests) == 1

    def test_search_truncates_to_max_results(self, wikibase):
        # A page holds up to 50 results, so a max_results that is not a multiple of 50 would overshoot without truncation
        wikibase.search_results = [{'id': f'Q{i}', 'label': f'result {i}', 'match': {}} for i in range(200)]

        results = search_entities('rivaroxaban', max_results=60)
        assert len(results) == 60
        assert results[-1] == 'Q59'

        # Only the pages needed to reach 60 results are fetched (2 x 50), not the whole dataset
        search_requests = [r for r in wikibase.requests if r.get('action') == 'wbsearchentities']
        assert len(search_requests) == 2

    def test_search_dict_result(self, wikibase):
        wikibase.search_results = [{'id': 'Q1', 'label': 'result', 'match': {}, 'description': 'a description', 'aliases': ['alias']}]

        results = search_entities('anything', dict_result=True)
        assert results[0]['id'] == 'Q1'
        assert results[0]['description'] == 'a description'
        assert results[0]['aliases'] == ['alias']

    def test_search_language_parameter(self, wikibase):
        wikibase.search_results = []
        search_entities('anything', language='fr')
        assert wikibase.last_request['language'] == 'fr'

        search_entities('anything')
        assert wikibase.last_request['language'] == str(wbi_config['DEFAULT_LANGUAGE'])

    def test_search_strict_language_and_limit_parameters(self, wikibase):
        wikibase.search_results = [{'id': f'Q{i}', 'label': f'result {i}', 'match': {}} for i in range(20)]

        results = search_entities('anything', strict_language=True, max_results=10)
        assert 'strictlanguage' in wikibase.last_request
        assert wikibase.last_request['limit'] == '10'
        assert len(results) == 10


class TestEmptyValues:
    """A snak of the 'value' type without value is rejected before the write, with an explicit error (#496)."""

    @staticmethod
    def _item(*claims):
        item = WikibaseIntegrator().item.new()
        item.claims.add(list(claims))
        return item

    @pytest.mark.parametrize('claim', [String(value='', prop_nr='P1'), String(value=None, prop_nr='P1'), Item(prop_nr='P1'), Time(prop_nr='P1'),
                                       MonolingualText(text='', language='en', prop_nr='P1')])
    def test_empty_claim(self, wikibase, claim):
        with pytest.raises(EmptyValueError, match='Missing value for: claim P1. Set a value, or use the WikibaseSnakType.NO_VALUE') as excinfo:
            self._item(claim).write(allow_anonymous=True)

        assert isinstance(excinfo.value, ValueError)
        # Nothing was sent to the Wikibase instance
        assert not wikibase.edits

    def test_empty_qualifier_and_reference(self, wikibase):
        claim = String(value='abc', prop_nr='P1', qualifiers=[Time(prop_nr='P585')], references=[[String(value='', prop_nr='P854')]])

        with pytest.raises(EmptyValueError) as excinfo:
            self._item(claim).write(allow_anonymous=True)

        assert 'qualifier P585 of a P1 claim' in str(excinfo.value)
        assert 'reference P854 of a P1 claim' in str(excinfo.value)

    def test_all_problems_are_listed(self, wikibase):
        with pytest.raises(EmptyValueError, match='Missing value for: claim P1, claim P2. '):
            self._item(String(value='', prop_nr='P1'), String(value='', prop_nr='P2')).write(allow_anonymous=True)

    def test_values_are_written(self, wikibase):
        """No value and unknown value snaks, and falsy values like 0, are valid."""
        item = self._item(String(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE), String(prop_nr='P2', snaktype=WikibaseSnakType.UNKNOWN_VALUE),
                          Quantity(amount=0, prop_nr='P3', qualifiers=[String(prop_nr='P4', snaktype=WikibaseSnakType.NO_VALUE)]))

        item.write(allow_anonymous=True)

        assert len(wikibase.edits) == 1

    def test_removed_statement_is_not_checked(self, wikibase):
        data = {'claims': [{'id': 'Q1$abc', 'mainsnak': {'snaktype': 'value', 'property': 'P1'}, 'type': 'statement', 'remove': ''}]}
        edit_entity(data=data, id='Q582', allow_anonymous=True)

    def test_mediainfo_statements(self, wikibase):
        data = {'statements': {'P180': [{'mainsnak': {'snaktype': 'value', 'property': 'P180', 'datavalue': {}}, 'type': 'statement'}]}}

        with pytest.raises(EmptyValueError, match='claim P180'):
            edit_entity(data=data, id='M1', allow_anonymous=True)

    def test_lexeme_forms_and_senses(self, wikibase):
        empty_claims = {'P1': [{'mainsnak': {'snaktype': 'value', 'property': 'P1', 'datavalue': {}}, 'type': 'statement'}]}
        data = {'forms': [{'add': '', 'claims': empty_claims}], 'senses': [{'id': 'L5-S1', 'claims': empty_claims}]}

        with pytest.raises(EmptyValueError, match=r'form \(new\): claim P1, sense L5-S1: claim P1'):
            edit_entity(data=data, id='L5', allow_anonymous=True)

    def test_lexeme_add_form(self, wikibase):
        data = {'representations': {'en': {'language': 'en', 'value': 'test'}}, 'grammaticalFeatures': [],
                'claims': [{'mainsnak': {'snaktype': 'value', 'property': 'P1', 'datavalue': {}}, 'type': 'statement'}]}

        with pytest.raises(EmptyValueError, match='claim P1'):
            lexeme_add_form('L5', data=data, allow_anonymous=True)

        assert 'wbladdform' not in [request.get('action') for request in wikibase.requests]


class TestCheckWikibase:
    """check_wikibase() reports the features of the instance and the problems found (#501)."""

    def test_instance_with_lexemes(self, wikibase):
        result = check_wikibase()

        assert result.mediawiki_version == 'MediaWiki 1.43.0'
        assert result.concept_base_uri == f'{wikibase.base_url}/entity/'
        assert result.is_wikibase and result.has_lexemes and result.has_search
        assert not result.has_mediainfo and not result.has_quality_constraints
        assert 'wikibase-lexeme' in result.datatypes
        assert result.sparql_available is True
        assert not result.problems
        # Two API requests: siteinfo and paraminfo
        assert [request.get('action') for request in wikibase.requests] == ['query', 'paraminfo']

        report = str(result)
        assert 'Lexemes: yes, MediaInfo: no, Search (WikibaseCirrusSearch): yes' in report
        assert f'SPARQL endpoint: {wikibase.sparql_endpoint_url} (available)' in report
        assert 'No problem found' in report

    def test_lexeme_extension_without_lexeme_support(self, wikibase):
        """Like Wikimedia Commons: WikibaseLexeme is installed, but the instance doesn't serve lexemes."""
        wikibase.entity_types = ['mediainfo']
        wikibase.extensions = ['WikibaseLexeme', 'WikibaseMediaInfo', 'WikibaseQualityConstraints', 'WikibaseRepository']

        result = check_wikibase(check_sparql=False)

        assert not result.has_lexemes
        assert result.has_mediainfo and result.has_quality_constraints
        assert not result.has_search

    def test_wikibase_url_mismatch(self, wikibase):
        result = check_wikibase(wikibase_url='http://www.wikidata.org', check_sparql=False)

        assert len(result.problems) == 1
        assert f"set config['WIKIBASE_URL'] to '{wikibase.base_url}'" in result.problems[0]
        assert 'Problems:' in str(result)

    def test_trailing_slash_is_not_a_mismatch(self, wikibase):
        assert not check_wikibase(wikibase_url=wikibase.base_url + '/', check_sparql=False).problems

    def test_not_a_wikibase(self, wikibase):
        wikibase.entity_types = []

        result = check_wikibase(check_sparql=False)

        assert not result.is_wikibase
        assert 'not a Wikibase repository' in result.problems[0]

    def test_sparql_endpoint_not_available(self, wikibase, requests_mock):
        sparql = requests_mock.post(wikibase.sparql_endpoint_url, status_code=503)

        result = check_wikibase()

        assert result.sparql_available is False
        assert 'is not available' in result.problems[0]
        assert '(not available)' in str(result)
        # A single attempt, without retries
        assert sparql.call_count == 1

    def test_sparql_not_checked(self, wikibase):
        result = check_wikibase(check_sparql=False)

        assert result.sparql_available is None
        assert result.sparql_endpoint_url is None
        assert not wikibase.sparql_queries
        assert '(not checked)' in str(result)


class TestSplitLargeWrites:
    """A write larger than the maximum request size is split into several edits (#463)."""

    MAX = 1500

    @staticmethod
    def _sent_size(edit):
        # The form-encoded size of the 'data' parameter, as sent in the request body
        return len(quote_plus(edit['params']['data']))

    @staticmethod
    def _new_item(claims=40):
        item = WikibaseIntegrator().item.new()
        item.labels.set('en', 'A large item')
        item.descriptions.set('en', 'An item with many statements')
        item.claims.add([String(value=f'value number {number}', prop_nr='P1') for number in range(claims)])
        return item

    def test_small_write_is_not_split(self, wikibase):
        self._new_item(claims=2).write(allow_anonymous=True, max_request_size=10_000)

        assert len(wikibase.edits) == 1

    def test_not_split_by_default(self, wikibase):
        assert wbi_config['MAX_REQUEST_SIZE'] is None

        self._new_item(claims=200).write(allow_anonymous=True)

        assert len(wikibase.edits) == 1

    def test_new_entity(self, wikibase):
        item = self._new_item().write(allow_anonymous=True, max_request_size=self.MAX)

        assert len(wikibase.edits) > 2
        first, *others = wikibase.edits
        # The first edit creates the entity with everything but the statements, and as many statements as fit
        assert first['params']['new'] == 'item'
        assert first['data']['labels']['en']['value'] == 'A large item'
        # The next edits only add statements to the created entity
        assert all(edit['params']['id'] == item.id and 'new' not in edit['params'] and set(edit['data']) == {'claims'} for edit in others)
        assert all(self._sent_size(edit) <= self.MAX for edit in wikibase.edits)
        # Every statement is written once, in order
        sent = [statement['mainsnak']['datavalue']['value'] for edit in wikibase.edits for statement in edit['data']['claims']]
        assert sent == [f'value number {number}' for number in range(40)]
        # The returned entity is the one of the last edit, with every statement
        assert len(item.claims.get('P1')) == 40
        assert len(wikibase.entities[item.id]['claims']['P1']) == 40

    def test_config(self, wikibase):
        wbi_config['MAX_REQUEST_SIZE'] = self.MAX

        self._new_item().write(allow_anonymous=True)

        assert len(wikibase.edits) > 2

    def test_existing_entity_clear_and_baserevid_on_the_first_edit_only(self, wikibase):
        wikibase.add_entity({'pageid': 1, 'ns': 0, 'title': 'Q1', 'lastrevid': 7, 'type': 'item', 'id': 'Q1', 'labels': {}, 'descriptions': {}, 'aliases': {},
                             'sitelinks': {}, 'claims': {}})
        data = self._new_item().get_json()

        edit_entity(data=data, id='Q1', clear=True, baserevid=7, allow_anonymous=True, max_request_size=self.MAX)

        assert len(wikibase.edits) > 2
        assert all(edit['params']['id'] == 'Q1' for edit in wikibase.edits)
        assert [('clear' in edit['params'], 'baserevid' in edit['params']) for edit in wikibase.edits] == [(True, True)] + [(False, False)] * (len(wikibase.edits) - 1)
        assert len(wikibase.entities['Q1']['claims']['P1']) == 40

    def test_statement_larger_than_the_maximum(self, wikibase):
        item = self._new_item(claims=3)
        item.claims.add(String(value='x' * (2 * self.MAX), prop_nr='P2'))

        with pytest.raises(ValueError, match='A statement of property P2 is larger than the maximum request size'):
            item.write(allow_anonymous=True, max_request_size=self.MAX)

        assert not wikibase.edits

    def test_data_without_statements_larger_than_the_maximum(self, wikibase):
        item = self._new_item(claims=3)
        item.descriptions.set('fr', 'y' * (2 * self.MAX))

        with pytest.raises(ValueError, match="without its statements is larger than the maximum request size"):
            item.write(allow_anonymous=True, max_request_size=self.MAX)

        assert not wikibase.edits

    def test_partial_failure(self, wikibase, monkeypatch):
        """An edit failing after the first one keeps its type, with a note telling what was saved."""
        original = wikibase._action_wbeditentity  # pylint: disable=protected-access

        def fail_second_edit(params):
            if len(wikibase.edits) == 1:
                wikibase.edits.append({'params': params, 'data': None})
                return {'error': {'code': 'failed-save', 'info': 'The save has failed.'}}
            return original(params)

        monkeypatch.setattr(wikibase, '_action_wbeditentity', fail_second_edit)

        with pytest.raises(MWApiError) as excinfo:
            self._new_item().write(allow_anonymous=True, max_request_size=self.MAX)

        created = next(iter(wikibase.entities))
        assert any('only the first 1 were saved' in note and created in note for note in excinfo.value.__notes__)
        assert wikibase.entities[created]['labels']['en']['value'] == 'A large item'

    def test_mediainfo_statements_and_removals(self):
        statements = {'P180': [{'mainsnak': {'snaktype': 'value', 'property': 'P180', 'datavalue': {'value': f'v{n}', 'type': 'string'}}, 'type': 'statement'}
                               for n in range(30)]
                      + [{'id': 'M1$abc', 'remove': ''}]}

        parts = wbi_helpers._split_entity_data({'labels': {}, 'statements': statements}, self.MAX)  # pylint: disable=protected-access

        assert len(parts) > 1
        assert all(set(part) <= {'labels', 'statements'} for part in parts)
        assert sum(len(part['statements']) for part in parts) == 31
        assert parts[-1]['statements'][-1] == {'id': 'M1$abc', 'remove': ''}

    def test_computed_size_is_the_sent_size(self):
        """The size is computed by parts, without serializing each growing part: it must match the real serialization."""
        data = self._new_item(claims=60).get_json()

        parts = wbi_helpers._split_entity_data(data, self.MAX)  # pylint: disable=protected-access

        sizes = [len(quote_plus(ujson.dumps(part))) for part in parts]
        assert all(size <= self.MAX for size in sizes)
        # Each part is full: adding the first statement of the next part would exceed the maximum
        for part, next_part in zip(parts, parts[1:]):
            grown = dict(part, claims=part['claims'] + next_part['claims'][:1])
            assert len(quote_plus(ujson.dumps(grown))) > self.MAX


class TestCheckConstraints:
    def test_requires_entity_id_or_claim_id(self):
        with pytest.raises(ValueError):
            check_constraints()

    def test_check_by_entity_id(self, wikibase):
        wikibase.constraint_results = {
            'Q582': [{'id': 'Q582$1', 'results': [{'status': 'violation', 'property': 'P17'}]}]
        }

        result = check_constraints(entity_id='Q582')
        assert wikibase.last_request['action'] == 'wbcheckconstraints'
        assert wikibase.last_request['id'] == 'Q582'
        assert result['claims']['Q582'][0]['results'][0]['status'] == 'violation'

    def test_check_by_multiple_entity_ids(self, wikibase):
        wikibase.constraint_results = {
            'Q582': [{'id': 'Q582$1', 'results': []}],
            'Q1': [{'id': 'Q1$1', 'results': []}],
        }

        check_constraints(entity_id=['Q582', 'Q1'])
        assert wikibase.last_request['id'] == 'Q582|Q1'

    def test_check_by_claim_id(self, wikibase):
        check_constraints(claim_id='Q582$1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a')
        assert wikibase.last_request['claimid'] == 'Q582$1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a'

    def test_check_with_status_filter(self, wikibase):
        check_constraints(entity_id='Q582', status=['violation', 'warning'])
        assert wikibase.last_request['status'] == 'violation|warning'


TIME_1850 = {'value': {'time': '+1850-03-03T00:00:00Z', 'timezone': 0, 'before': 0, 'after': 0, 'precision': 11, 'calendarmodel': 'http://www.wikidata.org/entity/Q1985727'},
             'type': 'time'}


class TestParseValue:
    def test_parse_value(self, wikibase):
        wikibase.parsed_values = {'3 March 1850': TIME_1850}

        results = parse_value('3 March 1850', datatype='time')
        assert results == [{'raw': '3 March 1850', **TIME_1850}]

        request = wikibase.last_request
        assert request['action'] == 'wbparsevalue'
        assert request['datatype'] == 'time'
        assert request['values'] == '3 March 1850'
        assert not {'property', 'options', 'validate'} & request.keys()

    def test_parse_value_failure(self, wikibase):
        # A value which can't be parsed is reported in its result, the other values are still parsed
        wikibase.parsed_values = {'3 March 1850': TIME_1850}

        results = parse_value(['foo bar', '3 March 1850'], datatype='time')
        assert [result['raw'] for result in results] == ['foo bar', '3 March 1850']
        assert results[0]['error'] == 'ValueParsers\\ParseException'
        assert results[0]['messages'][0]['name'] == 'wikibase-parse-error'
        assert results[1]['value'] == TIME_1850['value']

    def test_parse_value_parameters(self, wikibase):
        wikibase.parsed_values = {'1 février 1850': TIME_1850}

        results = parse_value(['1 février 1850'], prop_nr='P569', options={'lang': 'fr'}, validate=True)
        assert 'valid' in results[0]

        request = wikibase.last_request
        assert request['property'] == 'P569'
        assert ujson.loads(request['options']) == {'lang': 'fr'}
        assert 'validate' in request
        assert 'datatype' not in request

    def test_parse_value_pipe(self, wikibase):
        wikibase.parsed_values = {'a|b': {'value': 'a|b', 'type': 'string'}, 'c': {'value': 'c', 'type': 'string'}}

        results = parse_value(['a|b', 'c'], datatype='string')
        assert [result['value'] for result in results] == ['a|b', 'c']
        assert wikibase.last_request['values'] == '\x1fa|b\x1fc'

    def test_parse_value_batches(self, wikibase):
        values = [str(number) for number in range(120)]
        wikibase.parsed_values = {value: {'value': value, 'type': 'string'} for value in values}

        results = parse_value(values, datatype='string')
        assert [result['raw'] for result in results] == values
        assert [len(request['values'].split('|')) for request in wikibase.requests] == [50, 50, 20]

    @pytest.mark.parametrize('arguments', [{}, {'datatype': 'time', 'prop_nr': 'P569'}])
    def test_parse_value_invalid(self, wikibase, arguments):
        with pytest.raises(ValueError):
            parse_value('foo', **arguments)

        assert not wikibase.requests

    def test_parse_value_request_error(self, wikibase):
        # An error without results (e.g. an unknown property) is raised
        wikibase.fail_next(code='no-such-entity', info='Could not find an entity with the ID "P99999".')
        with pytest.raises(NonExistentEntityError):
            parse_value('foo', prop_nr='P99999')


class TestGetAvailableBadges:
    def test_get_available_badges(self, wikibase):
        assert get_available_badges() == ['Q17437796', 'Q17437798']
        assert wikibase.last_request['action'] == 'wbavailablebadges'

    def test_get_available_badges_none(self, wikibase):
        # An instance without badges configured returns an empty list
        wikibase.badges = []
        assert not get_available_badges()


class TestFulltextSearch:
    def test_fulltext_search(self, wikibase):
        wikibase.fulltext_results = [{'ns': 0, 'title': 'Q582', 'pageid': 892, 'snippet': 'Villeurbanne'}]

        results = fulltext_search('Villeurbanne')
        assert results[0]['title'] == 'Q582'
        assert wikibase.last_request['list'] == 'search'
        assert wikibase.last_request['srsearch'] == 'Villeurbanne'


class TestEditHelpers:
    def test_merge_items(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        merge_items(from_id='Q1', to_id='Q2', login=login, ignore_conflicts=['description'])

        request = wikibase.last_request
        assert request['action'] == 'wbmergeitems'
        assert request['fromid'] == 'Q1'
        assert request['toid'] == 'Q2'
        assert request['ignoreconflicts'] == 'description'
        assert 'tags' not in request

    def test_merge_items_tags(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        merge_items(from_id='Q1', to_id='Q2', login=login, tags=['tag1', 'tag2'])

        assert wikibase.last_request['tags'] == 'tag1|tag2'

    def test_merge_multiple_items(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        to_id = merge_multiple_items(['Q100', 'q30', 'Q5', 'Q30'], login=login, ignore_conflicts=['description', 'sitelink'], tags=['tag1'])

        assert to_id == 'Q5'
        merges = [request for request in wikibase.requests if request.get('action') == 'wbmergeitems']
        assert [(request['fromid'], request['toid']) for request in merges] == [('Q30', 'Q5'), ('Q100', 'Q5')]
        assert all(request['ignoreconflicts'] == 'description|sitelink' for request in merges)
        assert all(request['tags'] == 'tag1' for request in merges)

    @pytest.mark.parametrize('item_ids', [[], ['Q1'], ['Q1', 'q1'], ['Q1', 'P2'], ['Q1', 'L3'], ['Q1', 'Qfoo'], ['Q1', '2']])
    def test_merge_multiple_items_invalid(self, wikibase, item_ids):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        with pytest.raises(ValueError):
            merge_multiple_items(item_ids, login=login)

        assert not wikibase.requests

    def test_merge_multiple_items_stops_on_error(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        wikibase.fail_next(code='failed-modify', info='Conflicting descriptions for language en.')
        with pytest.raises(MWApiError):
            merge_multiple_items(['Q1', 'Q2', 'Q3'], login=login)

        merges = [request for request in wikibase.requests if request.get('action') == 'wbmergeitems']
        assert [request['fromid'] for request in merges] == ['Q2']

    def test_set_claim_new(self, wikibase, item_q582):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        claim = String(prop_nr='P1', value='foo')
        result = set_claim(claim, entity_id='q582', login=login)

        request = wikibase.last_request
        assert request['action'] == 'wbsetclaim'
        sent = ujson.loads(request['claim'])
        entity_id, claim_uuid = sent['id'].split('$')
        assert entity_id == 'Q582'
        uuid.UUID(claim_uuid)
        assert sent['mainsnak']['datavalue']['value'] == 'foo'
        assert claim.id == sent['id']
        assert result['claim']['id'] == sent['id']
        assert [statement['id'] for statement in wikibase.entities['Q582']['claims']['P1']] == [sent['id']]
        assert not {'index', 'baserevid', 'summary', 'tags', 'ignoreduplicatemainsnak', 'bot'} & request.keys()

    def test_set_claim_replace(self, wikibase, item_q582):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        claim_id = 'Q582$F7F18824-9A1F-4FE2-BCB0-56EA3A32FFF3'
        claim = Item(prop_nr='P31', value='Q5', id=claim_id)
        set_claim(claim, entity_id='Q582', login=login)

        assert ujson.loads(wikibase.last_request['claim'])['id'] == claim_id
        assert claim.id == claim_id
        statements = wikibase.entities['Q582']['claims']['P31']
        assert len(statements) == 2
        assert statements[0]['id'] == claim_id
        assert statements[0]['mainsnak']['datavalue']['value']['id'] == 'Q5'

    def test_set_claim_parameters(self, wikibase, item_q582):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        set_claim(String(prop_nr='P1', value='foo'), entity_id='Q582', index=0, baserevid=1234, summary='a summary', tags=['tag1', 'tag2'], ignore_duplicate_mainsnak=True,
                  login=login, is_bot=True)

        request = wikibase.last_request
        assert request['index'] == '0'
        assert request['baserevid'] == '1234'
        assert request['summary'] == 'a summary'
        assert request['tags'] == 'tag1|tag2'
        assert 'ignoreduplicatemainsnak' in request
        assert 'bot' in request

    def test_set_claim_duplicate_ignored(self, wikibase, item_q582, monkeypatch):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        claim = String(prop_nr='P1', value='foo')
        # With ignoreduplicatemainsnak, the API answers with a warning and no statement when the main snak already exists
        monkeypatch.setattr(wikibase, '_action_wbsetclaim', lambda params: {'warnings': {'wbsetclaim': {'*': 'Duplicate main snak.'}}})
        result = set_claim(claim, entity_id='Q582', ignore_duplicate_mainsnak=True, login=login)

        assert 'claim' not in result
        assert claim.id is None

    @pytest.mark.parametrize('claim, entity_id', [
        (String(prop_nr='P1', value='foo'), None),
        (String(prop_nr='P1', value='foo', id='Q582$F7F18824-9A1F-4FE2-BCB0-56EA3A32FFF3'), 'Q1'),
    ])
    def test_set_claim_invalid(self, wikibase, claim, entity_id):
        with pytest.raises(ValueError):
            set_claim(claim, entity_id=entity_id)

        assert not wikibase.requests

    def test_set_claim_removed(self, wikibase):
        claim = String(prop_nr='P1', value='foo', id='Q582$F7F18824-9A1F-4FE2-BCB0-56EA3A32FFF3')
        claim.remove()
        with pytest.raises(ValueError):
            set_claim(claim)

        assert not wikibase.requests

    def test_set_claim_empty_value(self, wikibase):
        with pytest.raises(EmptyValueError):
            set_claim(String(prop_nr='P1'), entity_id='Q582')

        assert not wikibase.requests

    def test_create_redirect(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        result = create_redirect(from_id='Q1', to_id='Q2', login=login)

        assert result == {'success': 1, 'redirect': 'Q2'}
        request = wikibase.last_request
        assert request['action'] == 'wbcreateredirect'
        assert request['from'] == 'Q1'
        assert request['to'] == 'Q2'
        assert 'bot' not in request

    def test_create_redirect_bot(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        create_redirect(from_id='Q1', to_id='Q2', login=login, is_bot=True)

        assert 'bot' in wikibase.last_request

    def test_create_redirect_origin_not_empty(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        wikibase.fail_next(code='origin-not-empty', info='The origin item is not empty.')
        with pytest.raises(MWApiError):
            create_redirect(from_id='Q1', to_id='Q2', login=login)

    def test_remove_claims(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        remove_claims(claim_id='Q582$1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a', login=login)

        request = wikibase.last_request
        assert request['action'] == 'wbremoveclaims'
        assert request['claim'] == 'Q582$1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a'

    def test_lexeme_form_and_sense_id_validation(self):
        with pytest.raises(ValueError):
            lexeme_remove_form('invalid-form-id')

        with pytest.raises(ValueError):
            lexeme_remove_sense('invalid-sense-id')

    def test_lexeme_edit_sense_sends_sense_id(self, wikibase):
        # The mock doesn't implement wbleditsenseelements, so the call fails, but the request parameters are still recorded
        with pytest.raises(MWApiError):
            lexeme_edit_sense('L10-S2', data={}, allow_anonymous=True)

        request = wikibase.last_request
        assert request['action'] == 'wbleditsenseelements'
        assert request['senseId'] == 'L10-S2'


class TestGenerateEntityInstances:
    def test_multiple_entities(self, wikibase, item_q582):
        wikibase.add_fixture('property_P50')
        wikibase.add_fixture('lexeme_L5')

        expected = {
            'Q582': ('item', 'ItemEntity'),
            'P50': ('property', 'PropertyEntity'),
            'L5': ('lexeme', 'LexemeEntity'),
        }

        entity_instances = generate_entity_instances(entities=list(expected.keys()))

        assert wikibase.last_request['ids'] == 'Q582|P50|L5'
        for entity_id, entity in entity_instances:
            etype, class_name = expected[entity_id]
            assert entity.ETYPE == etype
            assert type(entity).__name__ == class_name

    def test_single_entity(self, wikibase, item_q582):
        entity_instances = generate_entity_instances(entities='Q582')

        for entity_id, entity in entity_instances:
            assert entity_id == 'Q582'
            assert entity.ETYPE == 'item'

    def test_entities_are_requested_by_batches_of_50(self, wikibase, item_q582):
        # wbgetentities rejects more than 50 IDs with a 'toomanyvalues' error
        ids = [f'Q{n}' for n in range(1, 121)]
        for entity_id in ids:
            wikibase.entities[entity_id] = dict(copy.deepcopy(item_q582), id=entity_id, title=entity_id)

        entity_instances = generate_entity_instances(entities=ids)

        assert [entity_id for entity_id, _ in entity_instances] == ids
        batches = [request['ids'].split('|') for request in wikibase.requests if request.get('action') == 'wbgetentities']
        assert [len(batch) for batch in batches] == [50, 50, 20]

    def test_deleted_entity(self, wikibase, item_q582):
        # A deleted entity is returned as {'id': ..., 'missing': ''}, without its type
        wikibase.deleted_entities.add('Q9363993')

        with pytest.raises(MissingEntityException, match='Q9363993'):
            generate_entity_instances(entities=['Q582', 'Q9363993'])

    def test_unknown_entity_type(self, wikibase):
        wikibase.entities['X1'] = {'id': 'X1', 'type': 'unknown-type'}

        with pytest.raises(ValueError, match="Unknown entity type 'unknown-type' for the entity X1"):
            generate_entity_instances(entities='X1')

    def test_non_existent_entity(self, wikibase, item_q582):
        # An ID that never existed makes wbgetentities fail with 'no-such-entity'
        with pytest.raises(NonExistentEntityError):
            generate_entity_instances(entities=['Q582', 'Q999999999999'])


class TestSparql:
    def test_execute_sparql_query(self, wikibase):
        wikibase.sparql_bindings = [{'child': {'type': 'uri', 'value': wikibase.base_url + '/entity/Q106'}}]

        results = execute_sparql_query('SELECT ?child WHERE { ?child wdt:P22 wd:Q1339 . }')
        assert len(results['results']['bindings']) == 1

        # The query is prefixed with the tool comment
        assert 'WikibaseIntegrator' in wikibase.sparql_queries[-1]

    def test_execute_sparql_query_with_prefix(self, wikibase):
        wikibase.sparql_bindings = []
        prefix = 'PREFIX wd: <http://www.wikidata.org/entity/>'
        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', prefix=prefix)
        assert prefix in wikibase.sparql_queries[-1]

    def test_query_is_sent_in_request_body(self, wikibase, requests_mock):
        wikibase.sparql_bindings = []
        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }')

        last = requests_mock.last_request
        # The query travels in the form-encoded request body (not the URL), without the previous bogus multipart header
        assert 'query=' in (last.text or '')
        assert last.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded')

    def test_sparql_retry_on_429(self, wikibase, requests_mock):
        url = 'https://throttled.example.org/sparql'
        requests_mock.post(url, [
            {'status_code': 429, 'headers': {'retry-after': '1'}, 'text': 'Too Many Requests'},
            {'json': {'results': {'bindings': []}}, 'status_code': 200},
        ])

        results = execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, retry_after=1)
        assert results['results']['bindings'] == []
        assert requests_mock.call_count == 2

    @pytest.mark.parametrize('retry_after_header, expected_sleep', [('7', 7), ('Wed, 21 Oct 2015 07:28:00 GMT', 3)])
    def test_sparql_429_honours_retry_after(self, requests_mock, monkeypatch, retry_after_header, expected_sleep):
        url = 'https://throttled.example.org/sparql'
        requests_mock.post(url, [
            {'status_code': 429, 'headers': {'retry-after': retry_after_header}, 'text': 'Too Many Requests'},
            {'json': {'results': {'bindings': []}}, 'status_code': 200},
        ])
        slept = []
        # wbi_backoff waits between the tries: only the delay asked by the Query Service, no exponential delay on top
        monkeypatch.setattr('time.sleep', slept.append)
        monkeypatch.setattr('wikibaseintegrator.wbi_helpers.sleep', slept.append)

        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, retry_after=3)
        assert slept == [expected_sleep]

    def test_sparql_malformed_query_is_not_retried(self, requests_mock):
        url = 'https://example.org/sparql'
        requests_mock.post(url, status_code=400, text='MalformedQueryException')

        with pytest.raises(requests.HTTPError):
            execute_sparql_query('SELECT * WHERE {', endpoint=url)
        assert requests_mock.call_count == 1

    @pytest.mark.parametrize('status_code', [500, 502, 503, 504])
    def test_sparql_retry_on_server_error(self, requests_mock, status_code):
        url = 'https://unstable.example.org/sparql'
        requests_mock.post(url, [
            {'status_code': status_code, 'text': 'error'},
            {'json': {'results': {'bindings': []}}, 'status_code': 200},
        ])

        results = execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url)
        assert results['results']['bindings'] == []
        assert requests_mock.call_count == 2

    def test_sparql_persistent_server_error_raises(self, requests_mock):
        url = 'https://unstable.example.org/sparql'
        requests_mock.post(url, status_code=503, text='Service Unavailable')
        wbi_config['BACKOFF_MAX_TRIES'] = 3

        with pytest.raises(requests.HTTPError) as excinfo:
            execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url)
        assert excinfo.value.response.status_code == 503
        assert requests_mock.call_count == 3

    def test_sparql_retry_on_connection_error(self, requests_mock):
        url = 'https://unreachable.example.org/sparql'
        requests_mock.post(url, [
            {'exc': requests.exceptions.ConnectionError},
            {'json': {'results': {'bindings': []}}, 'status_code': 200},
        ])

        results = execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url)
        assert results['results']['bindings'] == []
        assert requests_mock.call_count == 2

    def test_sparql_max_retries_is_deprecated(self, requests_mock):
        url = 'https://public.example.org/sparql'
        requests_mock.post(url, json={'results': {'bindings': []}})

        with pytest.warns(DeprecationWarning, match='max_retries'):
            execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, max_retries=3)

    def test_sparql_basic_auth(self, requests_mock):
        url = 'https://protected.example.org/sparql'
        requests_mock.post(url, json={'results': {'bindings': []}})

        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, auth=('user', 'secret'))
        assert requests_mock.last_request.headers['Authorization'].startswith('Basic ')

    def test_sparql_auth_from_config(self, requests_mock):
        url = 'https://protected.example.org/sparql'
        requests_mock.post(url, json={'results': {'bindings': []}})
        wbi_config['SPARQL_AUTH'] = ('user', 'secret')

        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url)
        assert requests_mock.last_request.headers['Authorization'].startswith('Basic ')

    def test_sparql_no_auth_by_default(self, requests_mock):
        url = 'https://public.example.org/sparql'
        requests_mock.post(url, json={'results': {'bindings': []}})

        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url)
        assert 'Authorization' not in requests_mock.last_request.headers

    def test_sparql_extra_headers(self, requests_mock):
        url = 'https://protected.example.org/sparql'
        requests_mock.post(url, json={'results': {'bindings': []}})

        execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, headers={'Authorization': 'Bearer token'})
        last = requests_mock.last_request
        assert last.headers['Authorization'] == 'Bearer token'
        # The default headers are kept
        assert last.headers['Accept'] == 'application/sparql-results+json'
        assert 'WikibaseIntegrator' in last.headers['User-Agent']

    @pytest.mark.parametrize('status_code', [401, 403])
    def test_sparql_auth_failure_is_not_retried(self, requests_mock, status_code):
        url = 'https://protected.example.org/sparql'
        requests_mock.post(url, status_code=status_code, text='Unauthorized')

        with pytest.raises(requests.HTTPError):
            execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, auth=('user', 'wrong'), retry_after=0)
        assert requests_mock.call_count == 1


class TestDownloadEntityTtl:
    def test_download(self, wikibase, requests_mock):
        requests_mock.get(wikibase.base_url + '/entity/Q582.ttl', text='@prefix wd: <http://example.org/entity/> .')

        result = download_entity_ttl('Q582')
        assert result.startswith('@prefix')


class TestPureHelpers:
    def test_format_amount(self):
        assert format_amount(42) == '+42'
        assert format_amount(-42) == '-42'
        assert format_amount(42.0) == '+42'
        assert format_amount(42.5) == '+42.5'
        assert format_amount('42') == '+42'
        assert format_amount(0) == '+0'


@pytest.mark.filterwarnings("ignore:format2wbi.. is experimental:UserWarning")
class TestFormat2Wbi:
    def test_entity_types(self, wikibase):
        from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity

        assert isinstance(format2wbi('item', '{}'), ItemEntity)
        assert isinstance(format2wbi('property', '{}'), PropertyEntity)
        assert isinstance(format2wbi('lexeme', '{}'), LexemeEntity)
        assert isinstance(format2wbi('mediainfo', '{}'), MediaInfoEntity)
        with pytest.raises(ValueError):
            format2wbi('unknown', '{}')

    def test_item_from_simplified_json(self, wikibase):
        wikibase.add_property('P31', 'wikibase-item')
        wikibase.add_property('P1476', 'monolingualtext')
        wikibase.add_property('P2093', 'string')
        wikibase.add_property('P1545', 'string')
        wikibase.add_property('P953', 'url')

        result = format2wbi('item', '''{
          "labels": {"en": "an interesting article"},
          "descriptions": {"en": "scientific paper published in 2022"},
          "aliases": {"en": ["first alias", "second alias"]},
          "claims": {
            "P31": "Q13442814",
            "P1476": {"text": "an interesting article", "language": "en"},
            "P2093": [
              {"value": "First Author", "qualifiers": {"P1545": "1"}},
              {"value": "Second Author", "qualifiers": {"P1545": "2"}}
            ],
            "P953": "https://example.org/paper.pdf"
          }
        }''')

        assert result.labels.get('en') == 'an interesting article'
        assert result.descriptions.get('en') == 'scientific paper published in 2022'
        assert result.claims.get('P31')[0].mainsnak.datavalue['value']['id'] == 'Q13442814'
        assert len(result.claims.get('P2093')) == 2
