"""
Tests for the fastrun container. The SPARQL endpoint is served by the simulated
Wikibase instance, so the whole pipeline (statement loading, lazy qualifier /
reference / rank loading, comparison) runs offline and deterministically.
"""
import random
import re

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, EntitySchema, ExternalID, GeoShape, GlobeCoordinate, Item, Property, Quantity, String, TabularData, Time
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseRank, WikibaseSnakType

from .conftest import literal, uri

wbi = WikibaseIntegrator()

PTYPE_ENTITY_SCHEMA = 'http://wikiba.se/ontology#WikibaseEntitySchema'
PTYPE_EXTERNAL_ID = 'http://wikiba.se/ontology#ExternalId'
PTYPE_GEO_SHAPE = 'http://wikiba.se/ontology#GeoShape'
PTYPE_GLOBE_COORDINATE = 'http://wikiba.se/ontology#GlobeCoordinate'
PTYPE_ITEM = 'http://wikiba.se/ontology#WikibaseItem'
PTYPE_PROPERTY = 'http://wikiba.se/ontology#WikibaseProperty'
PTYPE_QUANTITY = 'http://wikiba.se/ontology#Quantity'
PTYPE_STRING = 'http://wikiba.se/ontology#String'
PTYPE_TABULAR_DATA = 'http://wikiba.se/ontology#TabularData'
PTYPE_TIME = 'http://wikiba.se/ontology#Time'
GEO_WKT_LITERAL = 'http://www.opengis.net/ont/geosparql#wktLiteral'
XSD_DATETIME = 'http://www.w3.org/2001/XMLSchema#dateTime'
XSD_DECIMAL = 'http://www.w3.org/2001/XMLSchema#decimal'
XSD_INTEGER = 'http://www.w3.org/2001/XMLSchema#integer'


class SparqlData:
    """
    Serve the SPARQL queries of the fastrun container from in-memory data.

    Each query type issued by the container (statement loading, qualifiers,
    references and ranks, language data) is recognized through its #Tool comment
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
        if 'wbi_fastrun._load_statement_details' in query:
            return self._statement_details(query)
        if 'wbi_fastrun._query_lang' in query:
            return self.labels
        if 'wbi_fastrun._load_value_details' in query:
            return self._value_details(query)
        if 'wbi_fastrun.load_statements' in query:
            match = re.search(r'/prop/(P\d+)> \?sid', query)
            assert match is not None
            bindings = self.statements.get(match.group(1), [])
            # Like a real endpoint, only bind the unit and the precision when the query selects them
            if '?unit' not in query.split('WHERE', 1)[0]:
                bindings = [{k: v for k, v in binding.items() if k not in ('unit', 'precision')} for binding in bindings]
            return bindings
        return []

    def _value_details(self, query: str) -> list[dict]:
        """The unit and the precision of the statements listed in the VALUES clause of the query."""
        match = re.search(r'VALUES \?sid \{ ([^}]+) \}', query)
        assert match is not None
        sids = set(re.findall(r'<([^>]+)>', match.group(1)))
        return [{k: v for k, v in binding.items() if k in ('sid', 'unit', 'precision')}
                for bindings in self.statements.values() for binding in bindings if binding['sid']['value'] in sids]

    def _statement_details(self, query: str) -> list[dict]:
        """The qualifiers, references and ranks requested by the query, of the statements listed in its VALUES clause."""
        match = re.search(r'VALUES \?sid \{ ([^}]+) \}', query)
        assert match is not None
        bindings = []
        for sid in re.findall(r'<([^>]+)>', match.group(1)):
            for pattern, bindings_by_sid in (('wikibase:qualifier', self.qualifiers), ('prov:wasDerivedFrom', self.references), ('wikibase:rank', self.ranks)):
                if pattern in query:
                    bindings += [{'sid': uri(sid), **binding} for binding in bindings_by_sid.get(sid, [])]
        return self._page(query, bindings)

    def _page(self, query: str, bindings: list[dict]) -> list[dict]:
        """
        Sort the rows like the ORDER BY of the query, then cut the page of its OFFSET and LIMIT. Like a real endpoint, the
        order of the rows the ORDER BY doesn't tell apart may change from one query to the next: here they are shuffled
        before the (stable) sort, differently for each query.
        """
        order = re.search(r'ORDER BY ([^\n]+)', query)
        keys = re.findall(r'\?(\w+)', order.group(1)) if order else []
        random.Random(len(self.wikibase.sparql_queries)).shuffle(bindings)
        bindings.sort(key=lambda binding: tuple(binding.get(key, {}).get('value', '') for key in keys))
        offset = re.search(r'OFFSET (\d+)', query)
        limit = re.search(r'LIMIT (\d+)', query)
        start = int(offset.group(1)) if offset else 0
        return bindings[start:start + int(limit.group(1))] if limit else bindings[start:]

    def statement(self, entity_id: str, prop_nr: str, value: dict, property_type: str, index: int = 0, unit: str | None = None, precision: int | None = None) -> str:
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
        if precision is not None:
            binding['precision'] = literal(str(precision), datatype=XSD_INTEGER)
        self.statements.setdefault(prop_nr, []).append(binding)
        return sid

    def qualifier(self, sid: str, prop_nr: str, value: dict, property_type: str, precision: int | None = None) -> None:
        binding = {
            'property': uri(f'{self.wikibase.base_url}/entity/{prop_nr}'),
            'value': value,
            'property_type': uri(property_type),
        }
        if precision is not None:
            binding['precision'] = literal(str(precision), datatype=XSD_INTEGER)
        self.qualifiers.setdefault(sid, []).append(binding)

    def reference(self, sid: str, prop_nr: str, value: dict, property_type: str, ref_node: str = 'deadbeef', precision: int | None = None) -> None:
        binding = {
            'srid': uri(f'{self.wikibase.base_url}/reference/{ref_node}'),
            'ref_property': uri(f'{self.wikibase.base_url}/entity/{prop_nr}'),
            'ref_value': value,
            'property_type': uri(property_type),
        }
        if precision is not None:
            binding['ref_precision'] = literal(str(precision), datatype=XSD_INTEGER)
        self.references.setdefault(sid, []).append(binding)

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

    def test_unknown_values_of_another_wikibase(self, wikibase, sparql_data, frc):
        """
        An unknown value of this instance (not Wikidata) is recognized: a time used to raise a KeyError, as its skolem IRI
        has no XSD datatype.
        """
        genid = f'{wikibase.base_url}/.well-known/genid/deadbeef'
        sparql_data.statement('Q99', 'P580', uri(genid), PTYPE_TIME)
        sparql_data.statement('Q99', 'P580', literal('2020-02-08T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, index=1, precision=11)

        frc.load_statements(claims=Time(time='+2020-02-08T00:00:00Z', prop_nr='P580'))

        assert frc.write_required(claims=[Time(time='+2020-02-08T00:00:00Z', prop_nr='P580')]) is False

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

    @pytest.mark.parametrize('datatype,prop_nr,value,other_value,property_type', [
        (EntitySchema, 'P12861', 'E10', 'E11', PTYPE_ENTITY_SCHEMA),
        (Property, 'P1659', 'P31', 'P279', PTYPE_PROPERTY),
    ], ids=['entity-schema', 'wikibase-property'])
    def test_entity_uri_datatypes(self, wikibase, sparql_data, frc, datatype, prop_nr, value, other_value, property_type):
        # EntitySchema used to raise a TypeError, and the statements of a Property were never matched (wrong PTYPE)
        sparql_data.statement('Q99', prop_nr, uri(f'{wikibase.base_url}/entity/{value}'), property_type)

        assert frc.write_required(claims=[datatype(value=value, prop_nr=prop_nr)]) is False
        assert frc.write_required(claims=[datatype(value=other_value, prop_nr=prop_nr)]) is True

    def test_globe_coordinate_truncated_by_the_query_service(self, wikibase, sparql_data, frc):
        # The query service returns the coordinates of Paris (Q90) truncated to 9 decimals: the local claim, with all its
        # decimals, was indexed by another string and always reported as requiring a write
        sparql_data.statement('Q99', 'P625', literal('Point(2.352222222 48.856666666)', datatype=GEO_WKT_LITERAL), PTYPE_GLOBE_COORDINATE)

        assert frc.write_required(claims=[GlobeCoordinate(latitude=48.85666666666667, longitude=2.352222222222222, prop_nr='P625')]) is False
        assert frc.write_required(claims=[GlobeCoordinate(latitude=48.857, longitude=2.352222222222222, prop_nr='P625')]) is True

    def test_globe_coordinate_of_another_globe(self, wikibase, sparql_data, frc):
        # The WKT literal of a coordinate on Mars (Q111) starts with the globe, it used to be skipped as invalid
        sparql_data.statement('Q99', 'P625', literal(f'<{wikibase.base_url}/entity/Q111> Point(354.5 -1.9)', datatype=GEO_WKT_LITERAL), PTYPE_GLOBE_COORDINATE)

        assert frc.write_required(claims=[GlobeCoordinate(latitude=-1.9, longitude=354.5, globe='Q111', prop_nr='P625')]) is False
        # The same point on the Moon (Q405)
        assert frc.write_required(claims=[GlobeCoordinate(latitude=-1.9, longitude=354.5, globe='Q405', prop_nr='P625')]) is True

    @pytest.mark.parametrize('cache', [True, False], ids=['complete-load', 'partial-load'])
    def test_statement_loads_are_totally_ordered(self, wikibase, sparql_data, cache):
        # Paged with OFFSET and LIMIT: ordered by ?sid only, the values of a statement (an EDTF value and the dates it
        # covers) could come in another order on the next page
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType, cache=cache)
        frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')])

        [query] = [query for query in wikibase.sparql_queries if 'wbi_fastrun.load_statements' in query]
        assert re.search(r'ORDER BY \?sid \?value\b', query)

    def test_commons_data_title_with_spaces(self, wikibase, sparql_data, frc):
        # The RDF export encodes a space of the page title as a '+', which used to be kept and never matched
        sparql_data.statement('Q99', 'P4179', uri('http://commons.wikimedia.org/data/main/Data:Population+FR+Q1657686.tab'), PTYPE_TABULAR_DATA)

        assert frc.write_required(claims=[TabularData(value='Data:Population FR Q1657686.tab', prop_nr='P4179')]) is False

    def test_partial_load_queries_the_commons_iri(self, wikibase, sparql_data):
        queries = []
        dispatch = sparql_data.dispatch
        wikibase.sparql_bindings = lambda query: (queries.append(query), dispatch(query))[1]
        sparql_data.statement('Q99', 'P3896', uri('http://commons.wikimedia.org/data/main/Data:Paris.map'), PTYPE_GEO_SHAPE)
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P3896')], base_data_type=BaseDataType, cache=False)

        assert frc.write_required(claims=[GeoShape(value='Data:Paris.map', prop_nr='P3896')]) is False
        assert any('<http://commons.wikimedia.org/data/main/Data:Paris.map>' in query for query in queries)

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

    def test_partial_load_qualifier_filter_uses_the_instance_iris(self, wikibase, sparql_data):
        # The qualifier filter of a partial load used the Wikidata pq: prefix and the default WIKIBASE_URL
        queries = []
        dispatch = sparql_data.dispatch
        wikibase.sparql_bindings = lambda query: (queries.append(query), dispatch(query))[1]
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType, cache=False, wikibase_url='https://other.example.org')

        frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q42', prop_nr='P1')])])

        assert any('?sid <https://other.example.org/prop/qualifier/P1> <https://other.example.org/entity/Q42>.' in query for query in queries)
        assert not any(' pq:' in query for query in queries)

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


class TestWriteRequiredExtensionDataTypes:
    """The data types of the Wikibase EDTF and Wikibase Local Media extensions."""

    def test_edtf(self, wikibase, sparql_data, frc):
        from wikibaseintegrator.datatypes.extra import EDTF

        # The EDTF literal, then the dates it covers: the statement has several ps: values. The property type used to
        # have no data type class, every value was skipped and a write always reported as required.
        sparql_data.statement('Q99', 'P1', literal('1985-04', datatype='http://www.w3.org/2001/XMLSchema#edtf'), 'http://wikiba.se/ontology#Edtf')
        sparql_data.statement('Q99', 'P1', literal('1985-04-01T00:00:00Z', datatype=XSD_DATETIME), 'http://wikiba.se/ontology#Edtf')

        assert frc.write_required(claims=[EDTF(value='1985-04', prop_nr='P1')]) is False
        assert frc.write_required(claims=[EDTF(value='1985-04-01T00:00:00Z', prop_nr='P1')]) is True

    def test_local_media(self, wikibase, sparql_data, frc):
        from wikibaseintegrator.datatypes.extra import LocalMedia

        sparql_data.statement('Q99', 'P2', uri('https://wiki.example.org/wiki/File:Bunny_rabbit.jpg'), 'http://wikiba.se/ontology#LocalMedia')

        assert frc.write_required(claims=[LocalMedia(value='Bunny rabbit.jpg', prop_nr='P2')]) is False
        assert frc.write_required(claims=[LocalMedia(value='Other.jpg', prop_nr='P2')]) is True


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


class TestWriteRequiredTimePrecision:
    """
    The SPARQL endpoint stores a timestamp with a precision lower than the day with '01' for the unknown month and day
    ('+1987-00-00T00:00:00Z' becomes '1987-01-01T00:00:00Z'), the precision is only on the value node.
    """

    @pytest.mark.parametrize('time, precision, expected', [
        ('+1987-00-00T00:00:00Z', 9, '+1987-01-01T00:00:00Z'),
        ('+1987-05-00T00:00:00Z', 10, '+1987-05-01T00:00:00Z'),
        ('+1987-05-17T00:00:00Z', 9, '+1987-01-01T00:00:00Z'),
        ('+1987-05-17T00:00:00Z', 10, '+1987-05-01T00:00:00Z'),
        ('+1987-05-17T00:00:00Z', 11, '+1987-05-17T00:00:00Z'),
        ('-13700000000-00-00T00:00:00Z', 1, '-13700000000-01-01T00:00:00Z'),
        ('+1987-00-00T00:00:00Z', None, '+1987-01-01T00:00:00Z'),
    ])
    def test_sparql_time(self, time, precision, expected):
        assert Time.sparql_time(time, precision) == expected

    @pytest.mark.parametrize('time, sparql_time, precision', [
        ('+1987-00-00T00:00:00Z', '1987-01-01T00:00:00Z', 9),
        ('+1987-01-01T00:00:00Z', '1987-01-01T00:00:00Z', 9),
        ('+1987-05-00T00:00:00Z', '1987-05-01T00:00:00Z', 10),
        ('+1987-05-17T00:00:00Z', '1987-05-17T00:00:00Z', 11),
    ])
    def test_matching_time(self, wikibase, sparql_data, frc, time, sparql_time, precision):
        sparql_data.statement('Q99', 'P577', literal(sparql_time, datatype=XSD_DATETIME), PTYPE_TIME, precision=precision)

        assert frc.write_required(claims=[Time(time=time, precision=precision, prop_nr='P577')]) is False

    def test_different_precision(self, wikibase, sparql_data, frc):
        """The same timestamp with another precision is another value: 1987-01-01 is not the year 1987."""
        sparql_data.statement('Q99', 'P577', literal('1987-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, precision=11)

        assert frc.write_required(claims=[Time(time='+1987-00-00T00:00:00Z', precision=9, prop_nr='P577')]) is True
        assert frc.write_required(claims=[Time(time='+1987-01-01T00:00:00Z', precision=11, prop_nr='P577')]) is False

    def test_unknown_precision_requires_write(self, wikibase, sparql_data, frc):
        """Without the precision from the value node, a year can't be told from its first day: the write is kept."""
        sparql_data.statement('Q99', 'P577', literal('1987-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME)

        assert frc.write_required(claims=[Time(time='+1987-00-00T00:00:00Z', precision=9, prop_nr='P577')]) is True

    def test_partial_load_queries_the_stored_timestamp(self, wikibase, sparql_data):
        queries = []
        dispatch = sparql_data.dispatch
        wikibase.sparql_bindings = lambda query: (queries.append(query), dispatch(query))[1]
        sparql_data.statement('Q99', 'P577', literal('1987-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, precision=9)

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P577')], base_data_type=BaseDataType, cache=False)
        assert frc.write_required(claims=[Time(time='+1987-00-00T00:00:00Z', precision=9, prop_nr='P577')]) is False
        assert any('"+1987-01-01T00:00:00Z"^^xsd:dateTime' in query for query in queries)

    @pytest.mark.parametrize('time, sparql_time, precision, expected', [
        ('+2022-00-00T00:00:00Z', '2022-01-01T00:00:00Z', 9, False),
        ('+2022-07-00T00:00:00Z', '2022-07-01T00:00:00Z', 10, False),
        ('+2022-07-19T00:00:00Z', '2022-07-19T00:00:00Z', 11, False),
        ('+2022-00-00T00:00:00Z', '2022-01-01T00:00:00Z', 11, True),
    ])
    def test_time_qualifier(self, wikibase, sparql_data, frc, time, sparql_time, precision, expected):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P585', literal(sparql_time, datatype=XSD_DATETIME), PTYPE_TIME, precision=precision)

        claim = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Time(time=time, prop_nr='P585')])
        assert frc.write_required(claims=[claim]) is expected

    @pytest.mark.parametrize('time, precision, expected', [
        ('+2022-00-00T00:00:00Z', 9, False),
        ('+2022-00-00T00:00:00Z', 11, True),
    ])
    def test_time_reference(self, wikibase, sparql_data, frc, time, precision, expected):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)
        sparql_data.reference(sid, 'P577', literal('2022-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, precision=precision)

        claim = ExternalID(value='P40095', prop_nr='P352', references=[[Time(time=time, prop_nr='P577'), Item(value='Q1234', prop_nr='P248')]])
        assert frc.write_required(claims=[claim], use_references=True) is expected

    def test_unchanged_entity(self, wikibase, sparql_data):
        """Issue #380: an existing entity holding low precision dates, checked again without any change."""
        sparql_data.statement('Q99', 'P1476', literal('The secret war against Sweden'), PTYPE_STRING)
        sid = sparql_data.statement('Q99', 'P577', literal('1988-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, precision=9)
        sparql_data.qualifier(sid, 'P585', literal('2022-07-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME, precision=10)

        item = wbi.item.new()
        item.id = 'Q99'
        item.claims.add(String(value='The secret war against Sweden', prop_nr='P1476'))
        item.claims.add(Time(time='+1988-00-00T00:00:00Z', prop_nr='P577', qualifiers=[Time(time='+2022-07-00T00:00:00Z', prop_nr='P585')]))
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P1476'), BaseDataType(prop_nr='P577')]) is False


class TestValueDetails:
    """
    The unit of a quantity and the precision of a time are on the value node. Joining it for every statement makes the
    complete load of a large dataset exceed the query time limit of the SPARQL endpoint (e.g. the population of every
    commune of France on Wikidata), so they are only loaded for the statements holding the value of a claim.
    """
    UNITLESS = 'http://www.wikidata.org/entity/Q199'

    @pytest.mark.parametrize('claim', [Time(prop_nr='P570', snaktype=WikibaseSnakType.UNKNOWN_VALUE),
                                       Quantity(prop_nr='P1082', snaktype=WikibaseSnakType.NO_VALUE)], ids=['time', 'quantity'])
    def test_claim_without_a_known_value_requires_a_write(self, wikibase, sparql_data, frc, claim):
        # Such a claim can't be compared through SPARQL: it used to raise a KeyError in a debug log
        assert frc.write_required(claims=[claim]) is True

    @staticmethod
    def queries(wikibase, tool: str) -> list[str]:
        return [query for query in wikibase.sparql_queries if f'#Tool: WikibaseIntegrator wbi_fastrun.{tool}\n' in query]

    def population(self, sparql_data, entity_id: str, index: int = 0, unit: str = UNITLESS) -> str:
        return sparql_data.statement(entity_id, 'P1082', literal('+1234', datatype=XSD_DECIMAL), PTYPE_QUANTITY, index=index, unit=unit)

    def test_complete_load_does_not_join_the_value_nodes(self, wikibase, sparql_data, frc):
        self.population(sparql_data, 'Q99')

        frc.load_statements(claims=Quantity(amount=1234, prop_nr='P1082'))

        [query] = self.queries(wikibase, 'load_statements')
        assert '/prop/statement/value/' not in query
        assert 'OPTIONAL' not in query

    def test_only_the_statements_of_the_entity_filter_are_checked(self, wikibase, sparql_data, frc):
        sid = self.population(sparql_data, 'Q99')
        other_sid = self.population(sparql_data, 'Q100', index=1)

        assert frc.write_required(claims=[Quantity(amount=1234, prop_nr='P1082')], entity_filter='Q99') is False

        [query] = self.queries(wikibase, '_load_value_details')
        assert f'<{sid}>' in query
        assert f'<{other_sid}>' not in query

    def test_get_entities_only_checks_the_common_entities(self, wikibase, sparql_data, frc):
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sid = self.population(sparql_data, 'Q99')
        other_sid = self.population(sparql_data, 'Q100', index=1)

        assert frc.get_entities(claims=[ExternalID(value='P40095', prop_nr='P352'), Quantity(amount=1234, prop_nr='P1082')]) == ['Q99']

        [query] = self.queries(wikibase, '_load_value_details')
        assert f'<{sid}>' in query
        assert f'<{other_sid}>' not in query

    def test_value_details_are_cached(self, wikibase, sparql_data, frc):
        self.population(sparql_data, 'Q99')
        claim = Quantity(amount=1234, prop_nr='P1082')

        assert frc.write_required(claims=[claim]) is False
        assert frc.write_required(claims=[claim]) is False

        assert len(self.queries(wikibase, '_load_value_details')) == 1

    def test_value_details_are_loaded_in_batches(self, wikibase, sparql_data, frc, monkeypatch):
        monkeypatch.setattr(wbi_fastrun, 'VALUE_DETAILS_BATCH_SIZE', 2)
        for index in range(5):
            self.population(sparql_data, f'Q{100 + index}', index=index)

        assert frc.get_entities(claims=Quantity(amount=1234, prop_nr='P1082')) == [f'Q{100 + index}' for index in range(5)]

        assert len(self.queries(wikibase, '_load_value_details')) == 3

    def test_partial_load_reads_the_value_details(self, wikibase, sparql_data):
        self.population(sparql_data, 'Q99')

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P1082')], base_data_type=BaseDataType, cache=False)
        assert frc.write_required(claims=[Quantity(amount=1234, prop_nr='P1082')]) is False
        assert frc.write_required(claims=[Quantity(amount=1234, unit='Q712226', prop_nr='P1082')]) is True

        assert not self.queries(wikibase, '_load_value_details')

    def test_clear_resets_the_value_details(self, wikibase, sparql_data, frc):
        self.population(sparql_data, 'Q99')
        claim = Quantity(amount=1234, prop_nr='P1082')
        assert frc.write_required(claims=[claim]) is False

        # The unit changed on the instance: the container must not keep the previous one once cleared
        sparql_data.statements['P1082'][0]['unit'] = uri(f'{wikibase.base_url}/entity/Q712226')
        frc.clear()

        assert frc.write_required(claims=[claim]) is True


class TestStatementDetails:
    """
    The qualifiers, references and ranks of the statements to compare are loaded together, for several statements at
    once, instead of one query per statement and per kind.
    """

    @staticmethod
    def queries(wikibase) -> list[str]:
        return [query for query in wikibase.sparql_queries if '#Tool: WikibaseIntegrator wbi_fastrun._load_statement_details\n' in query]

    @staticmethod
    def sids(query: str) -> list[str]:
        match = re.search(r'VALUES \?sid \{ ([^}]+) \}', query)
        assert match is not None
        return re.findall(r'<([^>]+)>', match.group(1))

    @staticmethod
    def claim(qualifier: str = 'Q42') -> ExternalID:
        return ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value=qualifier, prop_nr='P642')], references=[[Item(value='Q1234', prop_nr='P248')]])

    def statement(self, wikibase, sparql_data, entity_id: str, index: int = 0, qualifier: str = 'Q42', rank: str = 'NormalRank') -> str:
        sid = sparql_data.statement(entity_id, 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=index)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/{qualifier}'), PTYPE_ITEM)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)
        sparql_data.rank(sid, rank)
        return sid

    def test_one_query_for_the_qualifiers_references_and_rank(self, wikibase, sparql_data, frc):
        self.statement(wikibase, sparql_data, 'Q99')

        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False

        [query] = self.queries(wikibase)
        assert 'wikibase:qualifier' in query and 'prov:wasDerivedFrom' in query and 'wikibase:rank' in query

    @pytest.mark.parametrize('use_references, use_rank', [(False, False), (True, False), (False, True)])
    def test_only_the_requested_details_are_queried(self, wikibase, sparql_data, frc, use_references, use_rank):
        self.statement(wikibase, sparql_data, 'Q99')

        assert frc.write_required(claims=[self.claim()], use_references=use_references, use_rank=use_rank) is False

        [query] = self.queries(wikibase)
        assert 'wikibase:qualifier' in query
        assert ('prov:wasDerivedFrom' in query) is use_references
        assert ('wikibase:rank' in query) is use_rank

    def test_different_rank_in_the_same_query(self, wikibase, sparql_data, frc):
        self.statement(wikibase, sparql_data, 'Q99', rank='PreferredRank')

        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is True
        assert len(self.queries(wikibase)) == 1

    def test_statements_are_loaded_in_batches(self, wikibase, sparql_data, frc, monkeypatch):
        monkeypatch.setattr(wbi_fastrun, 'STATEMENT_DETAILS_BATCH_SIZE', 2)
        sids = [self.statement(wikibase, sparql_data, f'Q{100 + index}', index=index, qualifier='Q43') for index in range(5)]

        # No entity holds the qualifier of the claim: every statement is compared
        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is True

        queries = self.queries(wikibase)
        assert len(queries) == 3
        assert sorted(sid for query in queries for sid in self.sids(query)) == sorted(sids)

    def test_the_first_entity_holding_the_claims_ends_the_check(self, wikibase, sparql_data, frc, monkeypatch):
        monkeypatch.setattr(wbi_fastrun, 'STATEMENT_DETAILS_BATCH_SIZE', 2)
        sids = [self.statement(wikibase, sparql_data, f'Q{100 + index}', index=index) for index in range(5)]

        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False

        [query] = self.queries(wikibase)
        assert self.sids(query) == sids[:2]

    def test_a_reference_node_shared_by_two_statements(self, wikibase, sparql_data, frc):
        # Identical references share their node in the RDF export: each statement keeps its own copy
        self.statement(wikibase, sparql_data, 'Q100', index=0, qualifier='Q43')
        self.statement(wikibase, sparql_data, 'Q101', index=1)

        assert frc.write_required(claims=[self.claim()], use_references=True) is False
        assert len(self.queries(wikibase)) == 1

    def test_details_are_cached(self, wikibase, sparql_data, frc):
        self.statement(wikibase, sparql_data, 'Q99')

        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False
        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False

        assert len(self.queries(wikibase)) == 1

    def test_details_missing_from_the_cache_are_loaded(self, wikibase, sparql_data, frc):
        self.statement(wikibase, sparql_data, 'Q99', rank='PreferredRank')

        assert frc.write_required(claims=[self.claim()]) is False
        # The rank wasn't loaded by the first check
        assert frc.write_required(claims=[self.claim()], use_rank=True) is True

        queries = self.queries(wikibase)
        assert len(queries) == 2
        assert 'wikibase:rank' in queries[1]

    def test_details_are_loaded_again_without_cache(self, wikibase, sparql_data):
        self.statement(wikibase, sparql_data, 'Q99')
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType, cache=False)

        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False
        assert frc.write_required(claims=[self.claim()], use_references=True, use_rank=True) is False

        assert len(self.queries(wikibase)) == 2

    def test_pages_hold_every_detail_once(self, wikibase, sparql_data, frc):
        sid = self.statement(wikibase, sparql_data, 'Q99')
        for qualifier in ('Q43', 'Q44', 'Q45', 'Q46'):
            sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/{qualifier}'), PTYPE_ITEM)
        sparql_data.reference(sid, 'P854', uri('https://example.org/'), 'http://wikiba.se/ontology#Url', ref_node='cafe')

        # 8 rows, 2 per page: with ORDER BY ?sid only, the rows of the statement were all tied, and the pages repeated
        # some of them and skipped others
        frc._load_statement_details([sid], use_qualifiers=True, use_references=True, use_rank=True, limit=2)

        assert len(self.queries(wikibase)) == 5
        assert sorted(qualifier.datavalue['value']['id'] for qualifier in frc._qualifiers_cache[sid]) == ['Q42', 'Q43', 'Q44', 'Q45', 'Q46']
        assert sorted(snak.property_number for reference in frc._references_cache[sid] for snak in reference) == ['P248', 'P854']
        assert frc._rank_cache[sid] == WikibaseRank.NORMAL

    def test_single_statement_loaders(self, wikibase, sparql_data, frc):
        sid = self.statement(wikibase, sparql_data, 'Q99', rank='DeprecatedRank')

        assert [qualifier.datavalue['value']['id'] for qualifier in frc._load_qualifiers(sid)] == ['Q42']
        assert len(frc._load_references(sid)) == 1
        assert frc._load_rank(sid) == WikibaseRank.DEPRECATED
        assert frc._load_rank(f'{wikibase.base_url}/entity/statement/Q99-missing') is None
        assert len(self.queries(wikibase)) == 4


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

    def _item(self, item_id: str | None, claims: list) -> ItemEntity:
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

    def test_replace_all_cleans_the_new_strings_too(self, wikibase, sparql_data, frc):
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        # The strings of the entity are stripped and deduplicated, the new ones used to be compared raw
        assert frc.check_language_data('Q582', [' Villeurbanne '], 'fr', 'label', action_if_exists=ActionIfExists.REPLACE_ALL) is False
        assert frc.check_language_data('Q582', ['Villeurbanne', 'villeurbanne'], 'fr', 'label', action_if_exists=ActionIfExists.REPLACE_ALL) is False

    @pytest.mark.parametrize('lang', ['fr', 'zh-hans', 'be-tarask', 'en-x-Q123'])
    def test_valid_language_codes(self, wikibase, sparql_data, frc, lang):
        frc.get_language_data('Q582', lang, 'label')

        assert f'FILTER (lang(?label) = "{lang}")' in wikibase.sparql_queries[-1]

    @pytest.mark.parametrize('lang', ['fr") . ?entity ?p ?o FILTER ("1', 'fr fr', '', 'fr_FR'])
    def test_invalid_language_code(self, wikibase, sparql_data, frc, lang):
        # The language code goes as is in the query
        with pytest.raises(ValueError, match='Invalid language code'):
            frc.get_language_data('Q582', lang, 'label')
        assert not wikibase.sparql_queries

    def test_unknown_language_data_type(self, wikibase, sparql_data, frc):
        # Used to raise a KeyError
        with pytest.raises(ValueError, match="Unknown language data type 'labels'"):
            frc.get_language_data('Q582', 'fr', 'labels')


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
