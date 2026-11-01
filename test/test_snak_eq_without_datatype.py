import pytest

from wikibaseintegrator.datatypes import Item, String
from wikibaseintegrator.entities import MediaInfoEntity
from wikibaseintegrator.models import Claims, Qualifiers, Reference, References, Snak
from wikibaseintegrator.wbi_enums import ActionIfExists

from .conftest import load_fixture


def depicts_statement() -> Item:
    """The P180 statement of the M75908279 fixture, built with WikibaseIntegrator: its snaks carry a datatype, unlike the ones of Commons."""
    qualifiers = Qualifiers()
    qualifiers.add(Item(prop_nr='P462', value='Q1088'))
    qualifiers.add(Item(prop_nr='P1419', value='Q161973'))
    return Item(prop_nr='P180', value='Q1653', qualifiers=qualifiers)


@pytest.fixture
def mediainfo() -> MediaInfoEntity:
    return MediaInfoEntity().from_json(load_fixture('mediainfo_M75908279'))


class TestSnakEquality:
    def test_snak_without_datatype(self):
        # Commons serves no datatype in the snaks of the MediaInfo statements: the property gives it
        without = Snak(property_number='P180', datavalue={'value': {'entity-type': 'item', 'numeric-id': 1653, 'id': 'Q1653'}, 'type': 'wikibase-entityid'})
        built = Item(prop_nr='P180', value='Q1653').mainsnak

        assert without == built
        assert built == without

    def test_different_datatypes_still_differ(self):
        assert String(prop_nr='P1', value='x').mainsnak != Snak(property_number='P1', datatype='external-id', datavalue=String(prop_nr='P1', value='x').mainsnak.datavalue)

    def test_reference_without_datatype(self):
        without = Reference().from_json({'hash': '0123abcd', 'snaks': {'P854': [{'snaktype': 'value', 'property': 'P854', 'datavalue': {'value': 'https://example.org', 'type': 'string'}}]},
                                         'snaks-order': ['P854']})
        built = Reference()
        built.add(String(prop_nr='P854', value='https://example.org'))

        assert without == built


class TestMediaInfoStatements:
    def test_built_statement_equals_the_statement_of_commons(self, mediainfo):
        assert depicts_statement() == mediainfo.claims.get('P180')[0]

    @pytest.mark.parametrize('action', [ActionIfExists.APPEND_OR_REPLACE, ActionIfExists.REPLACE_ALL, ActionIfExists.MERGE_REFS_OR_APPEND, ActionIfExists.KEEP])
    def test_adding_the_existing_statement_changes_nothing(self, mediainfo, action):
        mediainfo.claims.add(depicts_statement(), action_if_exists=action)

        statements = mediainfo.get_json()['statements']['P180']
        # The existing statement, without a duplicate or a removal
        assert [statement.get('id') for statement in statements] == [mediainfo.claims.get('P180')[0].id]
        assert 'remove' not in statements[0]

    def test_merge_refs_merges_into_the_statement_of_commons(self, mediainfo):
        claim = depicts_statement()
        reference = Reference()
        reference.add(String(prop_nr='P854', value='https://example.org'))
        claim.references = References().add(reference)

        mediainfo.claims.add(claim, action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)

        statements = mediainfo.get_json()['statements']['P180']
        assert len(statements) == 1
        assert statements[0]['id'] == mediainfo.claims.get('P180')[0].id
        assert len(statements[0]['references']) == 1

    def test_remove_a_qualifier_of_commons(self, mediainfo):
        qualifiers = mediainfo.claims.get('P180')[0].qualifiers
        qualifiers.remove(Item(prop_nr='P462', value='Q1088'))

        assert 'P462' not in qualifiers.get_json()

    def test_another_statement_is_appended(self, mediainfo):
        mediainfo.claims.add(Item(prop_nr='P180', value='Q42'), action_if_exists=ActionIfExists.APPEND_OR_REPLACE)

        assert len(mediainfo.get_json()['statements']['P180']) == 2


def test_claims_of_wikidata_keep_comparing_datatypes():
    claims = Claims().from_json({'P1': [{'mainsnak': {'snaktype': 'value', 'property': 'P1', 'datatype': 'string', 'datavalue': {'value': 'x', 'type': 'string'}},
                                         'type': 'statement', 'id': 'Q1$abc', 'rank': 'normal'}]})
    claims.add(String(prop_nr='P1', value='x'), action_if_exists=ActionIfExists.APPEND_OR_REPLACE)

    assert len(claims.get_json()['P1']) == 1
