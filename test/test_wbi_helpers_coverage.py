"""
Tests for the paths of wbi_helpers not covered by test_wbi_helpers.py: the optional parameters of the edit helpers, the
Lexeme form and sense helpers, and the edge cases of the request and data checks.
"""
import json

import pytest
import requests
import ujson

from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.wbi_exceptions import EmptyValueError, SearchError
from wikibaseintegrator.wbi_helpers import (edit_entity, lexeme_add_form, lexeme_add_sense, lexeme_edit_form, lexeme_edit_sense, lexeme_remove_form, lexeme_remove_sense,
                                            mediawiki_api_call, mediawiki_api_call_helper, merge_items, merge_lexemes, remove_claims, search_entities)


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


def _serve(wikibase, action, response):
    """Make the simulated instance answer an action it doesn't implement with a fixed response."""
    setattr(wikibase, f'_action_{action}', lambda params: response)


def _snak(prop_nr, value=None):
    snak = {'snaktype': 'value', 'property': prop_nr, 'datatype': 'string'}
    if value is not None:
        snak['datavalue'] = {'value': value, 'type': 'string'}
    return snak


def _statement(prop_nr, value=None):
    return {'mainsnak': _snak(prop_nr, value), 'type': 'statement', 'rank': 'normal'}


class TestParaminfoValues:
    @staticmethod
    def _paraminfo(*modules):
        return {'paraminfo': {'modules': list(modules)}}

    def test_values_of_the_parameter(self):
        json_data = self._paraminfo({'name': 'wbgetentities', 'parameters': [{'name': 'new', 'type': ['other']}]},
                                    {'name': 'wbeditentity', 'parameters': [{'name': 'id', 'type': 'string'}, {'name': 'new', 'type': ['item', 'property']}]})

        assert wbi_helpers._paraminfo_values(json_data, module='wbeditentity', parameter='new') == ['item', 'property']

    def test_parameter_without_a_list_of_values(self):
        json_data = self._paraminfo({'name': 'wbeditentity', 'parameters': [{'name': 'id', 'type': 'string'}, {'name': 'new', 'type': 'string'}]},
                                    {'name': 'wbeditentity', 'parameters': []})

        assert not wbi_helpers._paraminfo_values(json_data, module='wbeditentity', parameter='new')

    def test_unknown_module(self):
        assert not wbi_helpers._paraminfo_values(self._paraminfo({'name': 'query'}), module='wbeditentity', parameter='new')
        assert not wbi_helpers._paraminfo_values({}, module='wbeditentity', parameter='new')


class TestApiCallOptions:
    def test_reauthentication_of_a_request_without_token(self, wikibase):
        """A request without edit token is sent again as is after the re-authentication."""
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        wikibase.fail_next(code='assertuserfailed', info='You are no longer logged in.')

        result = mediawiki_api_call('POST', mediawiki_api_url=wikibase.mediawiki_api_url, login=login, data={'action': 'wbavailablebadges'})

        assert result['badges'] == wikibase.badges
        assert login.reauthenticate_calls == 1
        assert len(wikibase.requests) == 2
        assert all('token' not in request for request in wikibase.requests)

    def test_assert_given_by_the_caller_is_kept(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        mediawiki_api_call_helper(data={'action': 'wbavailablebadges', 'assert': 'bot'}, login=login)

        assert wikibase.last_request['assert'] == 'bot'
        assert wikibase.last_request['token'] == login.edit_token

    def test_maxlag_disabled(self, wikibase):
        mediawiki_api_call_helper(data={'action': 'wbavailablebadges'}, allow_anonymous=True, maxlag=0)

        assert 'maxlag' not in wikibase.last_request
        assert wikibase.last_request['assert'] == 'anon'

    def test_maxlag_sent_by_default(self, wikibase):
        mediawiki_api_call_helper(data={'action': 'wbavailablebadges'}, allow_anonymous=True)

        assert wikibase.last_request['maxlag'] == '5'


class TestCheckEmptyValues:
    @pytest.mark.parametrize('data', [None, [], 'Q1', 42])
    def test_data_that_is_not_an_entity(self, data):
        assert wbi_helpers._check_empty_values(data) is None

    def test_sub_entities_that_are_not_dictionaries_are_skipped(self):
        data = {'forms': ['L5-F1', {'id': 'L5-F2', 'claims': {'P1': [_statement('P1')]}}], 'senses': [None]}

        with pytest.raises(EmptyValueError) as excinfo:
            wbi_helpers._check_empty_values(data)

        assert str(excinfo.value).startswith('Missing value for: form L5-F2: claim P1.')

    def test_sub_entities_with_values(self):
        assert wbi_helpers._check_empty_values({'forms': ['L5-F1', {'claims': [_statement('P1', 'a')]}]}) is None


class TestSplitEntityData:
    def test_statements_as_a_list(self):
        statements = [_statement('P1', f'value {n}') for n in range(20)]
        data = {'labels': {'en': {'language': 'en', 'value': 'label'}}, 'claims': statements}
        max_request_size = len(ujson.dumps(data)) // 3

        parts = wbi_helpers._split_entity_data(data, max_request_size)

        assert len(parts) > 1
        assert parts[0]['labels'] == data['labels']
        assert all(set(part) == {'claims'} for part in parts[1:])
        assert [statement for part in parts for statement in part['claims']] == statements
        assert all(wbi_helpers._encoded_size(part) <= max_request_size for part in parts)


class TestEditEntity:
    def test_type_is_required_for_a_new_entity(self, wikibase):
        with pytest.raises(ValueError, match="'type' parameter is mandatory"):
            edit_entity(data={}, allow_anonymous=True)

        assert not wikibase.requests

    def test_tags(self, wikibase):
        edit_entity(data={}, type='item', tags=['tag-a', 'tag-b'], allow_anonymous=True)

        assert wikibase.last_edit['params']['tags'] == 'tag-a|tag-b'

    def test_site_and_title(self, wikibase):
        _serve(wikibase, 'wbeditentity', {'entity': {'id': 'Q1', 'type': 'item'}, 'success': 1})

        result = edit_entity(data={'labels': {}}, site='enwiki', title='Villeurbanne', allow_anonymous=True)

        assert result['entity']['id'] == 'Q1'
        request = wikibase.last_request
        assert (request['site'], request['title']) == ('enwiki', 'Villeurbanne')
        assert 'id' not in request and 'new' not in request


class TestEditHelpersOptions:
    def test_merge_items_as_bot(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        merge_items(from_id='Q2', to_id='Q1', login=login, is_bot=True)

        request = wikibase.last_request
        assert (request['fromid'], request['toid'], request['bot'], request['assert']) == ('Q2', 'Q1', '', 'bot')

    def test_merge_lexemes_without_summary_nor_bot(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        assert merge_lexemes(source='L1', target='L2', login=login) == {'success': 1}

        request = wikibase.last_request
        assert 'summary' not in request and 'bot' not in request
        assert request['assert'] == 'user'

    def test_remove_claims_options(self, wikibase):
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        remove_claims(claim_id='Q582$1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a', summary='cleanup', baserevid=1234, is_bot=True, login=login)

        request = wikibase.last_request
        assert (request['summary'], request['baserevid'], request['bot'], request['assert']) == ('cleanup', '1234', '', 'bot')


class TestSearchEntitiesFailure:
    def test_unsuccessful_search(self, wikibase):
        _serve(wikibase, 'wbsearchentities', {'search': [], 'success': 0})

        with pytest.raises(SearchError):
            search_entities('Villeurbanne')


class TestLexemeHelpers:
    """The optional parameters of the Lexeme helpers, and the form and sense helpers the simulated instance doesn't implement."""

    def test_add_form_options(self, wikibase):
        wikibase.add_fixture('lexeme_L5')
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        result = lexeme_add_form('L5', data={'representations': {}}, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login)

        assert result['success'] == 1
        params = wikibase.last_edit['params']
        assert (params['baserevid'], params['tags'], params['bot']) == ('12', 'tag-a|tag-b', '')

    def test_add_sense(self, wikibase):
        wikibase.add_fixture('lexeme_L5')
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        glosses = {'glosses': {'en': {'language': 'en', 'value': 'a gloss'}}}

        result = lexeme_add_sense('L5', data=glosses, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login)

        assert result['sense']['glosses'] == glosses['glosses']
        params = wikibase.last_edit['params']
        assert (params['action'], params['lexemeId'], params['baserevid'], params['tags'], params['bot']) == ('wbladdsense', 'L5', '12', 'tag-a|tag-b', '')
        assert json.loads(params['data']) == glosses

    def test_add_sense_without_options(self, wikibase):
        wikibase.add_fixture('lexeme_L5')

        lexeme_add_sense('L5', data={'glosses': {}}, allow_anonymous=True)

        assert not {'baserevid', 'tags', 'bot'} & set(wikibase.last_edit['params'])

    @pytest.mark.parametrize('form_id', ['L5-F1', 'http://www.wikidata.org/entity/L5-F1'])
    def test_edit_form(self, wikibase, form_id):
        _serve(wikibase, 'wbleditformelements', {'form': {'id': 'L5-F1'}, 'success': 1})
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        data = {'representations': {'en': {'language': 'en', 'value': 'colours'}}}

        assert lexeme_edit_form(form_id, data=data, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login)['success'] == 1

        request = wikibase.last_request
        assert (request['action'], request['formId'], request['baserevid'], request['tags'], request['bot']) == ('wbleditformelements', 'L5-F1', '12', 'tag-a|tag-b', '')
        assert json.loads(request['data']) == data

    def test_edit_form_without_options(self, wikibase):
        _serve(wikibase, 'wbleditformelements', {'form': {'id': 'L5-F1'}, 'success': 1})

        lexeme_edit_form('L5-F1', data={}, allow_anonymous=True)

        assert not {'baserevid', 'tags', 'bot'} & set(wikibase.last_request)

    def test_edit_form_checks_empty_values(self, wikibase):
        with pytest.raises(EmptyValueError):
            lexeme_edit_form('L5-F1', data={'claims': {'P1': [_statement('P1')]}}, allow_anonymous=True)

        assert not wikibase.requests

    @pytest.mark.parametrize('function', [lexeme_edit_form, lexeme_edit_sense])
    def test_edit_invalid_id(self, wikibase, function):
        with pytest.raises(ValueError, match='Invalid'):
            function('L5', data={})

        assert not wikibase.requests

    @pytest.mark.parametrize('form_id', ['L5-F1', 'https://wikibase.example.org/entity/L5-F1'])
    def test_remove_form(self, wikibase, form_id):
        _serve(wikibase, 'wblremoveform', {'success': 1})
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        assert lexeme_remove_form(form_id, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login) == {'success': 1}

        request = wikibase.last_request
        assert (request['action'], request['id'], request['baserevid'], request['tags'], request['bot']) == ('wblremoveform', 'L5-F1', '12', 'tag-a|tag-b', '')

    def test_remove_form_without_options(self, wikibase):
        _serve(wikibase, 'wblremoveform', {'success': 1})

        lexeme_remove_form('L5-F1', allow_anonymous=True)

        assert not {'baserevid', 'tags', 'bot'} & set(wikibase.last_request)

    def test_edit_sense(self, wikibase):
        _serve(wikibase, 'wbleditsenseelements', {'sense': {'id': 'L5-S1'}, 'success': 1})
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)
        data = {'glosses': {'en': {'language': 'en', 'value': 'a gloss'}}}

        lexeme_edit_sense('http://www.wikidata.org/entity/L5-S1', data=data, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login)

        request = wikibase.last_request
        assert (request['senseId'], request['baserevid'], request['tags'], request['bot']) == ('L5-S1', '12', 'tag-a|tag-b', '')
        assert json.loads(request['data']) == data

    @pytest.mark.parametrize('sense_id', ['L5-S1', 'https://wikibase.example.org/entity/L5-S1'])
    def test_remove_sense(self, wikibase, sense_id):
        _serve(wikibase, 'wblremovesense', {'success': 1})
        login = FakeLogin(mediawiki_api_url=wikibase.mediawiki_api_url)

        assert lexeme_remove_sense(sense_id, baserevid=12, tags=['tag-a', 'tag-b'], is_bot=True, login=login) == {'success': 1}

        request = wikibase.last_request
        assert (request['action'], request['id'], request['baserevid'], request['tags'], request['bot']) == ('wblremovesense', 'L5-S1', '12', 'tag-a|tag-b', '')

    def test_remove_sense_without_options(self, wikibase):
        _serve(wikibase, 'wblremovesense', {'success': 1})

        lexeme_remove_sense('L5-S1', allow_anonymous=True)

        assert not {'baserevid', 'tags', 'bot'} & set(wikibase.last_request)
