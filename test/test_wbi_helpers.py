"""
Tests for wbi_helpers: low-level API call machinery (retries, maxlag, error
mapping), search, merge, SPARQL and the various pure helper functions.
"""
import logging

import pytest
import requests

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import AnonymousEditNotAllowedError, MaxRetriesReachedException, ModificationFailed, MWApiError, NonExistentEntityError, SaveFailed
from wikibaseintegrator.wbi_helpers import (download_entity_ttl, execute_sparql_query, format2wbi, format_amount, fulltext_search, generate_entity_instances, get_user_agent,
                                            lexeme_edit_sense, lexeme_remove_form, lexeme_remove_sense, mediawiki_api_call, mediawiki_api_call_helper, merge_items, remove_claims,
                                            search_entities)


class FakeLogin:
    """Minimal stand-in for wbi_login._Login, without any HTTP interaction."""

    def __init__(self, mediawiki_api_url, edit_token='fakelogintoken+\\'):
        self.mediawiki_api_url = mediawiki_api_url
        self.edit_token = edit_token
        self.session = requests.Session()

    def get_edit_token(self):
        return self.edit_token

    def get_session(self):
        return self.session


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

    def test_format_must_be_json(self):
        with pytest.raises(ValueError):
            mediawiki_api_call('POST', mediawiki_api_url='https://example.org/w/api.php', data={'format': 'xml'})


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

        results = execute_sparql_query('SELECT * WHERE { ?a ?b ?c . }', endpoint=url, max_retries=3, retry_after=1)
        assert results['results']['bindings'] == []


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
