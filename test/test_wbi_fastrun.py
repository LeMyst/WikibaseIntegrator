"""
Tests for the fastrun container. The SPARQL endpoint is served by the simulated
Wikibase instance, so the whole pipeline (statement loading, lazy qualifier /
reference / rank loading, comparison) runs offline and deterministically.
"""
import re

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, ExternalID, Item, Quantity, String, Time
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseRank

from .conftest import literal, uri

wbi = WikibaseIntegrator()

PTYPE_EXTERNAL_ID = 'http://wikiba.se/ontology#ExternalId'
PTYPE_ITEM = 'http://wikiba.se/ontology#WikibaseItem'
PTYPE_QUANTITY = 'http://wikiba.se/ontology#Quantity'
PTYPE_STRING = 'http://wikiba.se/ontology#String'
PTYPE_TIME = 'http://wikiba.se/ontology#Time'
XSD_DATETIME = 'http://www.w3.org/2001/XMLSchema#dateTime'
XSD_DECIMAL = 'http://www.w3.org/2001/XMLSchema#decimal'


class SparqlData:
    """
    Serve the SPARQL queries of the fastrun container from in-memory data.

    Each query type issued by the container (statement loading, qualifiers,
    references, rank, language data) is recognized through its #Tool comment
    and answered from the matching attribute.
    """

    def __init__(self, wikibase):
        self.wikibase = wikibase
        self.statements: dict[str, list[dict]] = {}  # property number -> bindings
        self.qualifiers: dict[str, list[dict]] = {}  # statement URI -> bindings
        self.references: dict[str, list[dict]] = {}  # statement URI -> bindings
        self.ranks: dict[str, list[dict]] = {}  # statement URI -> bindings
        self.labels: list[dict] = []  # language data bindings
        wikibase.sparql_bindings = self.dispatch

    def dispatch(self, query: str) -> list[dict]:
        if 'wbi_fastrun._load_qualifiers' in query:
            return self.qualifiers.get(self._sid(query), [])
        if 'wbi_fastrun._load_references' in query:
            return self.references.get(self._sid(query), [])
        if 'wbi_fastrun._load_rank' in query:
            return self.ranks.get(self._sid(query), [])
        if 'wbi_fastrun._query_lang' in query:
            return self.labels
        if 'wbi_fastrun.load_statements' in query:
            prop_nr = re.search(r'/prop/(P\d+)> \?sid', query).group(1)
            return self.statements.get(prop_nr, [])
        return []

    @staticmethod
    def _sid(query: str) -> str:
        return re.search(r'VALUES \?sid \{ <([^>]+)> \}', query).group(1)

    def statement(self, entity_id: str, prop_nr: str, value: dict, property_type: str, index: int = 0, unit: str | None = None) -> str:
        """Register a statement binding and return its statement URI."""
        sid = f'{self.wikibase.base_url}/entity/statement/{entity_id}-{prop_nr}-{index}'
        binding = {
            'entity': uri(f'{self.wikibase.base_url}/entity/{entity_id}'),
            'sid': uri(sid),
            'value': value,
            'property_type': uri(property_type),
        }
        if unit is not None:
            binding['unit'] = uri(unit)
        self.statements.setdefault(prop_nr, []).append(binding)
        return sid

    def qualifier(self, sid: str, prop_nr: str, value: dict, property_type: str) -> None:
        self.qualifiers.setdefault(sid, []).append({
            'property': uri(f'{self.wikibase.base_url}/entity/{prop_nr}'),
            'value': value,
            'property_type': uri(property_type),
        })

    def reference(self, sid: str, prop_nr: str, value: dict, property_type: str, ref_node: str = 'deadbeef') -> None:
        self.references.setdefault(sid, []).append({
            'srid': uri(f'{self.wikibase.base_url}/reference/{ref_node}'),
            'ref_property': uri(f'{self.wikibase.base_url}/entity/{prop_nr}'),
            'ref_value': value,
            'property_type': uri(property_type),
        })

    def rank(self, sid: str, rank: str) -> None:
        self.ranks[sid] = [{'rank': uri(f'http://wikiba.se/ontology#{rank}')}]

    def label(self, entity_id: str, value: str, lang: str) -> None:
        self.labels.append({
            'entity': uri(f'{self.wikibase.base_url}/entity/{entity_id}'),
            'label': literal(value, lang=lang),
        })


@pytest.fixture
def sparql_data(wikibase):
    return SparqlData(wikibase)


@pytest.fixture
def frc(wikibase):
    return wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)


class TestLoadStatements:
    def test_load_statements(self, wikibase, sparql_data, frc):
        """The container must query the SPARQL endpoint and store the data in its internal format."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))

        expected_key = ExternalID(value='P40095', prop_nr='P352').get_sparql_value()
        assert expected_key in frc.data['P352']
        assert frc.data['P352'][expected_key][0]['entity'] == f'{wikibase.base_url}/entity/Q99'
        assert frc.properties_type['P352'] == PTYPE_EXTERNAL_ID
        assert 'P352' in frc.loaded_complete

    def test_cache_reuse(self, wikibase, sparql_data, frc):
        """A complete load must be reused, without a new SPARQL query."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))
        queries_after_first_load = len(wikibase.sparql_queries)

        frc.load_statements(claims=ExternalID(value='something-else', prop_nr='P352'))
        assert len(wikibase.sparql_queries) == queries_after_first_load

    def test_partial_load_is_not_reused_as_cache(self, wikibase, sparql_data, frc):
        """A load restricted to a value (cache disabled) must not be reused as a complete cache."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'), cache=False)
        assert 'P352' not in frc.loaded_complete
        # The query is restricted to the value of the claim
        assert '"P40095"' in wikibase.sparql_queries[-1]

        # The next cached load must query the endpoint again
        queries_after_partial_load = len(wikibase.sparql_queries)
        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))
        assert len(wikibase.sparql_queries) > queries_after_partial_load
        assert 'P352' in frc.loaded_complete

    def test_unparseable_value_is_skipped(self, wikibase, sparql_data, frc):
        """A value the data type can't represent must be skipped, not crash the load."""
        # A timestamp with a time part: its precision can't be inferred by Time.set_value()
        sparql_data.statement('Q99', 'P580', literal('2020-02-08T12:34:56Z', datatype=XSD_DATETIME), PTYPE_TIME)
        sparql_data.statement('Q99', 'P580', literal('2020-02-08T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, index=1)

        frc.load_statements(claims=Time(time='+2020-02-08T00:00:00Z', prop_nr='P580'))

        assert len(frc.data['P580']) == 1

    def test_invalid_claims(self, frc):
        with pytest.raises(ValueError):
            frc.load_statements(claims='not a claim')


class TestGetEntities:
    def test_get_entities(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.statement('Q100', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=1)

        assert frc.get_entities(claims=ExternalID(value='P40095', prop_nr='P352')) == ['Q100', 'Q99']

    def test_get_entities_intersection(self, wikibase, sparql_data, frc):
        """With several claims, only the entities holding every value are returned."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.statement('Q100', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=1)
        sparql_data.statement('Q99', 'P828', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        claims = [ExternalID(value='P40095', prop_nr='P352'), Item(value='Q42', prop_nr='P828')]
        assert frc.get_entities(claims=claims) == ['Q99']

    def test_get_entities_no_match(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        assert frc.get_entities(claims=ExternalID(value='unknown-value', prop_nr='P352')) == []


class TestWriteRequired:
    def test_not_required_when_value_exists(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')]) is False

    def test_required_when_value_differs(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        assert frc.write_required(claims=[ExternalID(value='something-else', prop_nr='P352')]) is True

    def test_entity_filter(self, wikibase, sparql_data, frc):
        """The data exists on Q99: no write is required for Q99, a write is required for another entity."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        claims = [ExternalID(value='P40095', prop_nr='P352')]
        assert frc.write_required(claims=claims, entity_filter='Q99') is False
        assert frc.write_required(claims=claims, entity_filter='Q100') is True
        # A full entity URI is accepted too
        assert frc.write_required(claims=claims, entity_filter=f'{wikibase.base_url}/entity/Q99') is False

    def test_required_when_no_common_entity(self, wikibase, sparql_data, frc):
        """The two values exist, but on two different entities: a write is required."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.statement('Q100', 'P828', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        claims = [ExternalID(value='P40095', prop_nr='P352'), Item(value='Q42', prop_nr='P828')]
        assert frc.write_required(claims=claims) is True

    def test_not_required_when_common_entity(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.statement('Q99', 'P828', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        claims = [ExternalID(value='P40095', prop_nr='P352'), Item(value='Q42', prop_nr='P828')]
        assert frc.write_required(claims=claims) is False

    def test_property_filter(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        claims = [ExternalID(value='P40095', prop_nr='P352'), ExternalID(value='unchecked', prop_nr='P999')]
        # P999 is filtered out: only P352 is compared, no write is required
        assert frc.write_required(claims=claims, property_filter='P352') is False

    def test_required_when_no_claim_matches_the_property_filter(self, wikibase, sparql_data, frc):
        """When nothing can be verified, a write must be reported, not an error raised."""
        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], property_filter=['P999']) is True

    def test_force_append_always_requires_write(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        claims = [ExternalID(value='P40095', prop_nr='P352')]
        assert frc.write_required(claims=claims, action_if_exists=ActionIfExists.FORCE_APPEND) is True
        # The check short-circuits without querying the endpoint
        assert len(wikibase.sparql_queries) == 0

    def test_empty_claims(self, frc):
        with pytest.raises(ValueError):
            frc.write_required(claims=[])


class TestWriteRequiredQualifiers:
    def test_missing_qualifier_on_the_claim(self, wikibase, sparql_data, frc):
        """The statement has a qualifier, the claim doesn't: a write is required."""
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')]) is True

    def test_matching_qualifier(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        claim = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q42', prop_nr='P642')])
        assert frc.write_required(claims=[claim]) is False

    def test_different_qualifier_value(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        claim = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q43', prop_nr='P642')])
        assert frc.write_required(claims=[claim]) is True

    def test_qualifiers_can_be_ignored(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], use_qualifiers=False) is False

    def test_duplicate_statements_do_not_mask_a_match(self, wikibase, sparql_data, frc):
        """
        The entity holds two statements with the same value, one with a qualifier and one without: a claim matching
        either of them requires no write, whatever the statement order.
        """
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=0)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=1)

        without_qualifier = ExternalID(value='P40095', prop_nr='P352')
        with_qualifier = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q42', prop_nr='P642')])
        assert frc.write_required(claims=[without_qualifier]) is False
        assert frc.write_required(claims=[with_qualifier]) is False


class TestWriteRequiredReferences:
    def test_references_ignored_by_default(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')]) is False

    def test_missing_reference_on_the_claim(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], use_references=True) is True

    def test_matching_reference(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)

        claim = ExternalID(value='P40095', prop_nr='P352', references=[[Item(value='Q1234', prop_nr='P248')]])
        assert frc.write_required(claims=[claim], use_references=True) is False

    def test_different_reference(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)

        claim = ExternalID(value='P40095', prop_nr='P352', references=[[Item(value='Q4321', prop_nr='P248')]])
        assert frc.write_required(claims=[claim], use_references=True) is True


class TestWriteRequiredRank:
    def test_matching_rank(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.rank(sid, 'NormalRank')

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], use_rank=True) is False

    def test_different_rank(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.rank(sid, 'PreferredRank')

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], use_rank=True) is True

    def test_rank_ignored_by_default(self, wikibase, sparql_data, frc):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.rank(sid, 'PreferredRank')

        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')]) is False


class TestWriteRequiredQuantityUnits:
    def test_different_unit_requires_write(self, wikibase, sparql_data, frc):
        """Two amounts only differing by their unit must not be considered equal."""
        sparql_data.statement('Q99', 'P2046', literal('+42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit=f'{wikibase.base_url}/entity/Q712226')

        assert frc.write_required(claims=[Quantity(amount=42, prop_nr='P2046')]) is True
        assert frc.write_required(claims=[Quantity(amount=42, unit='Q11573', prop_nr='P2046')]) is True
        assert frc.write_required(claims=[Quantity(amount=42, unit='Q712226', prop_nr='P2046')]) is False

    def test_unitless_quantity_q199_normalization(self, wikibase, sparql_data, frc):
        """The RDF always represents a unitless quantity with the Wikidata Q199 entity, even on another instance."""
        sparql_data.statement('Q99', 'P1082', literal('+1234', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit='http://www.wikidata.org/entity/Q199')

        assert frc.write_required(claims=[Quantity(amount=1234, prop_nr='P1082')]) is False
        assert frc.write_required(claims=[Quantity(amount=1234, unit='Q712226', prop_nr='P1082')]) is True

    def test_get_entities_with_unit(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P2046', literal('+42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit=f'{wikibase.base_url}/entity/Q712226')
        sparql_data.statement('Q100', 'P2046', literal('+42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, index=1, unit='http://www.wikidata.org/entity/Q199')

        assert frc.get_entities(claims=Quantity(amount=42, unit='Q712226', prop_nr='P2046')) == ['Q99']
        assert frc.get_entities(claims=Quantity(amount=42, prop_nr='P2046')) == ['Q100']


class TestCaseInsensitive:
    def test_case_insensitive_value(self, wikibase, sparql_data):
        sparql_data.statement('Q99', 'P1', literal('FooBar'), PTYPE_STRING)

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P1')], base_data_type=BaseDataType, case_insensitive=True)
        assert frc.write_required(claims=[String(value='foobar', prop_nr='P1')]) is False

    def test_case_sensitive_by_default(self, wikibase, sparql_data):
        sparql_data.statement('Q99', 'P1', literal('FooBar'), PTYPE_STRING)

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P1')], base_data_type=BaseDataType)
        assert frc.write_required(claims=[String(value='foobar', prop_nr='P1')]) is True
        assert frc.write_required(claims=[String(value='FooBar', prop_nr='P1')]) is False


class TestEntityWriteRequired:
    """write_required() through an entity: the check is restricted to the entity being edited."""

    def _item(self, item_id: str | None, claims: list) -> 'ItemEntity':  # noqa: F821
        item = wbi.item.new()
        if item_id:
            item.id = item_id
        for claim in claims:
            item.claims.add(claim)
        return item

    def test_not_required_when_the_entity_holds_the_data(self, wikibase, sparql_data):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        item = self._item('Q99', [ExternalID(value='P40095', prop_nr='P352')])
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352')]) is False

    def test_required_when_the_data_is_on_another_entity(self, wikibase, sparql_data):
        """Q100 is edited: the value existing on Q99 must not inhibit the write."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        item = self._item('Q100', [ExternalID(value='P40095', prop_nr='P352')])
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352')]) is True

    def test_new_entity_matches_any_entity(self, wikibase, sparql_data):
        """An entity without ID matches any entity holding the data (deduplication use case)."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        item = self._item(None, [ExternalID(value='P40095', prop_nr='P352')])
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352')]) is False

    def test_required_when_no_claim_matches_the_base_filter(self, wikibase, sparql_data):
        """No claim of the entity is covered by the base filter: nothing can be verified, a write is required."""
        item = self._item('Q99', [ExternalID(value='P40095', prop_nr='P999')])
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352')]) is True

    def test_force_append(self, wikibase, sparql_data):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        item = self._item('Q99', [ExternalID(value='P40095', prop_nr='P352')])
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352')], action_if_exists=ActionIfExists.FORCE_APPEND) is True


class TestLanguageData:
    def test_language_data_and_check(self, wikibase, sparql_data, frc):
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        assert frc.get_language_data('Q582', 'fr', 'label') == ['Villeurbanne']
        # The comparison is case insensitive
        assert frc.check_language_data('Q582', ['villeurbanne'], 'fr', 'label') is False
        assert frc.check_language_data('Q582', ['Lyon'], 'fr', 'label') is True

    def test_empty_language_data(self, wikibase, sparql_data, frc):
        assert frc.get_language_data('Q582', 'fr', 'label') == ['']
        assert frc.get_language_data('Q582', 'fr', 'aliases') == []

    def test_language_data_is_cached(self, wikibase, sparql_data, frc):
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        frc.get_language_data('Q582', 'fr', 'label')
        queries_after_first_load = len(wikibase.sparql_queries)
        frc.get_language_data('Q582', 'fr', 'label')
        assert len(wikibase.sparql_queries) == queries_after_first_load

    def test_replace_all_language_data(self, wikibase, sparql_data, frc):
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        assert frc.check_language_data('Q582', ['Villeurbanne'], 'fr', 'label', action_if_exists=ActionIfExists.REPLACE_ALL) is False
        assert frc.check_language_data('Q582', ['Villeurbanne', 'Lyon'], 'fr', 'label', action_if_exists=ActionIfExists.REPLACE_ALL) is True


class TestClear:
    def test_clear(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))
        frc.init_language_data('fr', 'label')

        frc.clear()

        assert not frc.data
        assert not frc.loaded_complete
        assert not frc.properties_type
        assert not frc.loaded_langs


class TestFastrunStore:
    def test_container_is_reused(self, wikibase):
        frc1 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])
        frc2 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])
        assert frc1 is frc2

    def test_different_parameters_create_new_container(self, wikibase):
        frc1 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])
        frc2 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P921')])
        frc3 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')], use_references=True)
        frc4 = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')], case_insensitive=True)
        assert len({id(frc) for frc in (frc1, frc2, frc3, frc4)}) == 4


class TestBaseFilter:
    def test_invalid_base_filter(self):
        with pytest.raises(ValueError):
            wbi_fastrun.FastRunContainer(base_filter=['P352'], base_data_type=BaseDataType)

    def test_base_filter_string(self, wikibase):
        """The three base filter forms must be translated to the expected SPARQL triples."""
        frc = wbi_fastrun.FastRunContainer(base_data_type=BaseDataType, base_filter=[
            BaseDataType(prop_nr='P352'),
            Item(value='Q55983715', prop_nr='P703'),
            [Item(value='Q3624078', prop_nr='P31'), Item(prop_nr='P279')],
        ])

        base_filter_string = frc._base_filter_string()
        assert f'?entity <{wikibase.base_url}/prop/direct/P352> ?zzP352 .' in base_filter_string
        assert f'?entity <{wikibase.base_url}/prop/direct/P703> <{wikibase.base_url}/entity/Q55983715> .' in base_filter_string
        assert f'?entity <{wikibase.base_url}/prop/direct/P31>/<{wikibase.base_url}/prop/direct/P279>* <{wikibase.base_url}/entity/Q3624078> .' in base_filter_string
