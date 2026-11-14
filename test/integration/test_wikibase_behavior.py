"""
The behaviors of Wikibase that the library relies on, checked with raw API calls on a real instance. The unit tests
simulate them: when one of these tests fails, Wikibase changed, and the library (and the simulated instance of
test/conftest.py) has to follow.
"""
import json
import uuid

import pytest

from wikibaseintegrator.wbi_exceptions import MWApiError
from wikibaseintegrator.wbi_helpers import delete_page, mediawiki_api_call_helper

pytestmark = pytest.mark.integration

# A unique run identifier so concurrent/repeated runs never collide.
RUN_ID = uuid.uuid4().hex[:10]


def term(language: str, value: str, **flags: str) -> dict:
    return {'language': language, 'value': value, **flags}


def string_claim(property_id: str, value: str, **fields: str) -> dict:
    return {'mainsnak': {'snaktype': 'value', 'property': property_id, 'datavalue': {'value': value, 'type': 'string'}}, 'type': 'statement', 'rank': 'normal', **fields}


@pytest.fixture(scope='module')
def created(login):
    """The entities created by the tests of this module, deleted at the end."""
    entity_ids: list[str] = []
    yield entity_ids
    if entity_ids:
        # The response of wbeditentity has no page title: the namespace of the entities depends on the configuration of the instance
        entities = mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': '|'.join(entity_ids), 'props': 'info', 'format': 'json'}, allow_anonymous=True)['entities']
        for entity in entities.values():
            delete_page(title=entity['title'], reason='WikibaseIntegrator integration test cleanup', login=login)


@pytest.fixture(scope='module')
def edit(login, created):
    """wbeditentity with the data given as a dict: returns the entity of the response."""

    def edit_entity(data: dict, **params: str) -> dict:
        entity = mediawiki_api_call_helper(data={'action': 'wbeditentity', 'data': json.dumps(data), 'format': 'json', **params}, login=login)['entity']
        if 'new' in params:
            created.append(entity['id'])
        return entity

    return edit_entity


@pytest.fixture(scope='module')
def property_id(edit) -> str:
    return edit({'labels': {'en': term('en', f'WBI behavior string property {RUN_ID}')}, 'datatype': 'string'}, new='property')['id']


def labelled(name: str) -> dict:
    return {'labels': {'en': term('en', f'WBI behavior {name} {RUN_ID}')}}


class TestTerms:
    def test_empty_list_of_aliases_keeps_them(self, edit):
        # Aliases.set(language, [], REPLACE_ALL) must mark the aliases for removal: an empty list leaves them
        item = edit({**labelled('aliases'), 'aliases': {'en': [term('en', 'a'), term('en', 'b')]}}, new='item')

        edited = edit({'aliases': {'en': []}}, id=item['id'])
        assert [alias['value'] for alias in edited['aliases']['en']] == ['a', 'b']

        edited = edit({'aliases': {'en': [term('en', 'a', remove=''), term('en', 'b', remove='')]}}, id=item['id'])
        assert 'en' not in (edited.get('aliases') or {})

    def test_empty_label_removes_it(self, edit):
        # LanguageValues.set(language, '') marks the value for removal, like Wikibase does with an empty value
        item = edit({'labels': {'en': term('en', f'WBI behavior label {RUN_ID}'), 'fr': term('fr', f'étiquette {RUN_ID}')}}, new='item')

        edited = edit({'labels': {'fr': term('fr', '')}}, id=item['id'])
        assert 'fr' not in edited['labels']
        assert edited['labels']['en']['value'] == f'WBI behavior label {RUN_ID}'


class TestNewEntity:
    def test_claim_with_the_guid_of_another_entity(self, edit, property_id):
        # write(as_new=True) leaves out the GUIDs of the claims, which belong to the entity the data was read from
        original = edit({**labelled('original'), 'claims': [string_claim(property_id, 'a value')]}, new='item')
        guid = original['claims'][property_id][0]['id']

        with pytest.raises(MWApiError):
            edit({**labelled('copy'), 'claims': [string_claim(property_id, 'a value', id=guid)]}, new='item')


class TestValues:
    @pytest.mark.parametrize('bound', ['upperBound', 'lowerBound'])
    def test_quantity_with_a_single_bound_is_rejected(self, edit, bound):
        # Quantity requires both bounds or none
        quantity_property = edit({'labels': {'en': term('en', f'WBI behavior quantity property {bound} {RUN_ID}')}, 'datatype': 'quantity'}, new='property')['id']
        claim = {'mainsnak': {'snaktype': 'value', 'property': quantity_property,
                              'datavalue': {'value': {'amount': '+5', 'unit': '1', bound: '+5'}, 'type': 'quantity'}}, 'type': 'statement', 'rank': 'normal'}

        with pytest.raises(MWApiError):
            edit({**labelled(f'quantity {bound}'), 'claims': [claim]}, new='item')


class TestTokens:
    def test_anonymous_token_with_a_logged_in_session(self, login):
        # A request made with the session of a login needs the edit token of the login, even when allow_anonymous is True
        with pytest.raises(MWApiError) as error:
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'new': 'item', 'data': json.dumps(labelled('token')), 'token': '+\\', 'format': 'json'},
                                      login=login, allow_anonymous=True)
        assert error.value.code == 'badtoken'
