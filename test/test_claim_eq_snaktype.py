import pytest

from wikibaseintegrator.datatypes import Item, String
from wikibaseintegrator.models import Claims
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseSnakType


def test_no_value_and_unknown_value_claims_differ():
    no_value = Item(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE)
    unknown_value = Item(prop_nr='P1', snaktype=WikibaseSnakType.UNKNOWN_VALUE)

    # Both have no datavalue: they used to compare equal
    assert no_value != unknown_value
    assert no_value == Item(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE)
    assert unknown_value == Item(prop_nr='P1', snaktype=WikibaseSnakType.UNKNOWN_VALUE)


def existing_unknown_value() -> Claims:
    return Claims().from_json({'P1': [{'mainsnak': {'snaktype': 'somevalue', 'property': 'P1', 'datatype': 'wikibase-item'},
                                       'type': 'statement', 'id': 'Q1$abc', 'rank': 'normal'}]})


def test_replace_all_replaces_an_unknown_value_with_no_value():
    claims = existing_unknown_value()
    claims.add(Item(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE), action_if_exists=ActionIfExists.REPLACE_ALL)

    statements = claims.get_json()['P1']
    # The unknown value is removed and the no value is added, instead of the no value being dropped
    assert [(statement.get('id'), statement['mainsnak']['snaktype'], 'remove' in statement) for statement in statements] == [('Q1$abc', 'somevalue', True), (None, 'novalue', False)]


@pytest.mark.parametrize('action', [ActionIfExists.APPEND_OR_REPLACE, ActionIfExists.MERGE_REFS_OR_APPEND])
def test_append_keeps_the_unknown_value(action):
    claims = existing_unknown_value()
    claims.add(Item(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE), action_if_exists=action)

    statements = claims.get_json()['P1']
    # A new statement: the existing unknown value is not overwritten in place
    assert [(statement.get('id'), statement['mainsnak']['snaktype']) for statement in statements] == [('Q1$abc', 'somevalue'), (None, 'novalue')]


def test_known_value_without_datavalue_differs_from_no_value():
    assert String(prop_nr='P1') != String(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE)
