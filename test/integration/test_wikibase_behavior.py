"""
The behaviors of Wikibase that the library relies on, checked with raw API calls on a real instance. The unit tests
simulate them: when one of these tests fails, Wikibase changed, and the library (and the simulated instance of
test/conftest.py) has to follow.
"""
import json
import uuid

import pytest

from wikibaseintegrator.wbi_exceptions import MWApiError
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

pytestmark = pytest.mark.integration

# A unique run identifier so concurrent/repeated runs never collide.
RUN_ID = uuid.uuid4().hex[:10]


def term(language: str, value: str, **flags: str) -> dict:
    return {'language': language, 'value': value, **flags}


def string_claim(property_id: str, value: str, **fields: str) -> dict:
    return {'mainsnak': {'snaktype': 'value', 'property': property_id, 'datavalue': {'value': value, 'type': 'string'}}, 'type': 'statement', 'rank': 'normal', **fields}


@pytest.fixture(scope='module')
def created(delete_entities):
    """The entities created by the tests of this module, deleted at the end."""
    entity_ids: list[str] = []
    yield entity_ids
    delete_entities(entity_ids)


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
    @staticmethod
    def aliases(entity_id: str) -> list[str]:
        entity = mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': entity_id, 'props': 'aliases', 'format': 'json'}, allow_anonymous=True)['entities'][entity_id]
        return [alias['value'] for alias in (entity.get('aliases') or {}).get('en', [])]

    def test_empty_list_of_aliases_removes_them(self, edit):
        # Aliases.set(language, [], REPLACE_ALL) sends an empty list for the language
        item = edit({**labelled('aliases'), 'aliases': {'en': [term('en', 'a'), term('en', 'b')]}}, new='item')
        assert self.aliases(item['id']) == ['a', 'b']

        edit({'aliases': {'en': []}}, id=item['id'])
        assert self.aliases(item['id']) == []

    def test_aliases_marked_for_removal(self, edit):
        # Aliases.set(language) or set(language, None) marks the aliases for removal
        item = edit({**labelled('removed aliases'), 'aliases': {'en': [term('en', 'a'), term('en', 'b')]}}, new='item')

        edit({'aliases': {'en': [term('en', 'a', remove='')]}}, id=item['id'])
        assert self.aliases(item['id']) == ['b']

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


class TestEditResponse:
    # The page of the entity, in wbgetentities but not in the response of wbeditentity: after write(), the entity can't take
    # its page from the response (#1217), and the simulated instance of test/conftest.py answers the same way
    PAGE_FIELDS = {'pageid', 'ns', 'title', 'modified'}

    def test_new_entity(self, edit):
        entity = edit(labelled('edit response'), new='item')
        assert {'id', 'type', 'lastrevid'} <= set(entity)
        assert not self.PAGE_FIELDS & set(entity), sorted(entity)

    def test_existing_entity(self, edit):
        item_id = edit(labelled('edited response'), new='item')['id']
        entity = edit({'descriptions': {'en': term('en', 'an edit')}}, id=item_id)
        assert {'id', 'type', 'lastrevid'} <= set(entity)
        assert not self.PAGE_FIELDS & set(entity), sorted(entity)

        # wbgetentities has them
        fetched = mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': item_id, 'format': 'json'}, allow_anonymous=True)['entities'][item_id]
        assert self.PAGE_FIELDS <= set(fetched), sorted(fetched)


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
