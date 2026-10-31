"""
Tests of the fast run container completing test_wbi_fastrun.py: the argument checks, the paging of the statement loads,
the values the container can't represent, the base filter forms and the language data edge cases. The SPARQL endpoint
is served by the simulated Wikibase instance, through the SparqlData helper of test_wbi_fastrun.py.
"""
import logging
import re

import pytest

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, ExternalID, Item, String, Time
from wikibaseintegrator.models import Claims, Snak
from wikibaseintegrator.wbi_enums import WikibaseSnakType

from .conftest import literal, uri
from .test_wbi_fastrun import PTYPE_EXTERNAL_ID, PTYPE_ITEM, PTYPE_STRING, PTYPE_TIME, XSD_DATETIME, SparqlData

PTYPE_UNKNOWN = 'http://wikiba.se/ontology#SomethingNew'
LOAD_STATEMENTS_TOOL = '#Tool: WikibaseIntegrator wbi_fastrun.load_statements\n'


class PagedSparqlData(SparqlData):
    """SparqlData whose statement loads are cut in pages by their OFFSET and LIMIT, like a real endpoint."""

    def dispatch(self, query: str) -> list[dict]:
        bindings = super().dispatch(query)
        if LOAD_STATEMENTS_TOOL in query:
            return self._page(query, list(bindings))
        return bindings


@pytest.fixture
def sparql_data(wikibase):
    return SparqlData(wikibase)


@pytest.fixture
def frc(wikibase):
    return wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)


def load_statements_queries(wikibase) -> list[str]:
    return [query for query in wikibase.sparql_queries if LOAD_STATEMENTS_TOOL in query]


class TestArgumentChecks:
    @pytest.mark.parametrize('claims', ['not a claim', [ExternalID(value='P40095', prop_nr='P352'), 'not a claim'], None])
    def test_get_entities_invalid_claims(self, wikibase, sparql_data, frc, claims):
        with pytest.raises(ValueError, match='claims must be an instance of Claim or Claims or a list of Claim'):
            frc.get_entities(claims=claims)
        assert not wikibase.sparql_queries

    def test_get_entities_empty_claims(self, wikibase, sparql_data, frc):
        with pytest.raises(ValueError, match='claims must have at least one claim'):
            frc.get_entities(claims=[])
        with pytest.raises(ValueError, match='claims must have at least one claim'):
            frc.get_entities(claims=Claims())

    @pytest.mark.parametrize('claims', ['not a claim', [ExternalID(value='P40095', prop_nr='P352'), 42]])
    def test_write_required_invalid_claims(self, wikibase, sparql_data, frc, claims):
        with pytest.raises(ValueError, match='claims must be an instance of Claim or Claims or a list of Claim'):
            frc.write_required(claims=claims)
        assert not wikibase.sparql_queries

    def test_write_required_single_claim(self, wikibase, sparql_data, frc):
        """A single Claim is accepted like a list of one claim."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        assert frc.write_required(claims=ExternalID(value='P40095', prop_nr='P352')) is False
        assert frc.write_required(claims=ExternalID(value='other', prop_nr='P352')) is True

    def test_claims_object(self, wikibase, sparql_data, frc):
        """A Claims object is accepted by load_statements(), get_entities() and write_required()."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        claims = Claims().add(ExternalID(value='P40095', prop_nr='P352'))

        frc.load_statements(claims=claims)
        assert 'P352' in frc.loaded_complete
        assert frc.get_entities(claims=claims) == ['Q99']
        assert frc.write_required(claims=claims) is False

    @pytest.mark.parametrize('method', ['_load_qualifiers', '_load_references', '_load_rank'])
    def test_statement_loaders_reject_a_non_string_sid(self, wikibase, sparql_data, frc, method):
        with pytest.raises(ValueError, match='sid must be a string'):
            getattr(frc, method)(42)
        assert not wikibase.sparql_queries


class TestPaging:
    @pytest.fixture
    def paged_data(self, wikibase):
        data = PagedSparqlData(wikibase)
        for index, entity_id in enumerate(('Q100', 'Q101', 'Q102')):
            data.statement(entity_id, 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=index)
        return data

    @pytest.mark.parametrize('limit, pages', [(2, 2), (1, 4), (3, 2), (10, 1)])
    def test_complete_load_reads_every_page(self, wikibase, paged_data, frc, limit, pages):
        """The load goes on while a page is full, then stops on the first page shorter than the limit."""
        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'), limit=limit)

        queries = load_statements_queries(wikibase)
        assert len(queries) == pages
        assert [int(re.search(r'OFFSET (\d+)', query).group(1)) for query in queries] == [page * limit for page in range(pages)]
        assert all(f'LIMIT {limit}' in query for query in queries)
        assert sorted(statement['entity'].rsplit('/', 1)[-1] for statement in frc.data['P352']['"P40095"']) == ['Q100', 'Q101', 'Q102']
        assert 'P352' in frc.loaded_complete

    def test_partial_load_reads_every_page(self, wikibase, paged_data, frc):
        frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'), cache=False, limit=2)

        assert len(load_statements_queries(wikibase)) == 2
        assert len(frc.data['P352']['"P40095"']) == 3
        assert 'P352' not in frc.loaded_complete

    def test_write_required_query_limit(self, wikibase, paged_data, frc):
        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], query_limit=1) is False
        assert len(load_statements_queries(wikibase)) == 4


class TestUnrepresentableValues:
    def test_statement_of_an_unknown_property_type_is_skipped(self, wikibase, sparql_data, frc, caplog):
        """A property type no data type class implements leaves the value out of the dataset, with a warning."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_UNKNOWN)
        sparql_data.statement('Q100', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID, index=1)

        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_fastrun'):
            frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))

        assert [statement['entity'].rsplit('/', 1)[-1] for statement in frc.data['P352']['"P40095"']] == ['Q100']
        assert f"No data type class found for the property type '{PTYPE_UNKNOWN}'" in caplog.text

    def test_datatype_class(self, frc):
        assert frc._datatype_class(PTYPE_TIME) is Time
        with pytest.raises(ValueError, match=f"No data type class found for the property type '{PTYPE_UNKNOWN}'"):
            frc._datatype_class(PTYPE_UNKNOWN)

    def test_unrepresentable_qualifier_is_left_out(self, wikibase, sparql_data, frc, caplog):
        """
        A qualifier the container can't represent is left out of the qualifiers of the statement, so that the comparison
        fails safely: a write is reported as required.
        """
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.qualifier(sid, 'P642', uri(f'{wikibase.base_url}/entity/Q42'), PTYPE_ITEM)
        sparql_data.qualifier(sid, 'P1545', literal('1'), PTYPE_UNKNOWN)

        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_fastrun'):
            qualifiers = frc._load_qualifiers(sid)

        assert [qualifier.property_number for qualifier in qualifiers] == ['P642']
        assert f"Skipping a qualifier of statement '{sid}'" in caplog.text
        # The property type is recorded even when the value is skipped
        assert frc.properties_type['P1545'] == PTYPE_UNKNOWN
        assert frc.properties_type['P642'] == PTYPE_ITEM

        claim = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q42', prop_nr='P642'), String(value='1', prop_nr='P1545')])
        assert frc.write_required(claims=[claim]) is True

    def test_unrepresentable_reference_snak_is_left_out(self, wikibase, sparql_data, frc, caplog):
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P248', uri(f'{wikibase.base_url}/entity/Q1234'), PTYPE_ITEM)
        # A timestamp with a time part: its precision can't be inferred
        sparql_data.reference(sid, 'P813', literal('2020-02-08T12:34:56Z', datatype=XSD_DATETIME), PTYPE_TIME)

        with caplog.at_level(logging.WARNING, logger='wikibaseintegrator.wbi_fastrun'):
            references = frc._load_references(sid)

        assert [[snak.property_number for snak in reference] for reference in references] == [['P248']]
        assert f"Skipping a reference snak of statement '{sid}'" in caplog.text
        assert frc.properties_type['P813'] == PTYPE_TIME

    def test_reference_made_only_of_unrepresentable_snaks(self, wikibase, sparql_data, frc):
        """A reference whose every snak is left out is left out too."""
        sid = sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        sparql_data.reference(sid, 'P854', literal('x'), PTYPE_UNKNOWN)

        assert len(frc._load_references(sid)) == 0
        assert frc.write_required(claims=[ExternalID(value='P40095', prop_nr='P352')], use_references=True) is False


class TestValueKeys:
    def test_datatype_without_a_sparql_value(self, wikibase, sparql_data, frc, monkeypatch):
        """
        A known value whose data type has no SPARQL value (get_sparql_value() may return None) has no key: it can't be
        compared and a write is required.
        """
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        claim = ExternalID(value='P40095', prop_nr='P352')
        monkeypatch.setattr(claim, 'get_sparql_value', lambda **kwargs: None)

        assert frc._value_key(claim) is None
        assert frc.write_required(claims=[claim]) is True

    def test_claim_without_a_datavalue(self, wikibase, sparql_data, frc):
        """A claim whose datavalue is None has no value type, and matches no entity."""
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)
        claim = ExternalID(prop_nr='P352')
        claim.mainsnak.snaktype = WikibaseSnakType.NO_VALUE
        claim.mainsnak.datavalue = None

        assert frc._value_type(claim) is None
        assert frc.get_entities(claims=claim) == []
        assert frc.write_required(claims=claim) is True

    def test_value_type(self):
        assert wbi_fastrun.FastRunContainer._value_type(Time(time='+2020-02-08T00:00:00Z', prop_nr='P580')) == 'time'
        assert wbi_fastrun.FastRunContainer._value_type(ExternalID(prop_nr='P352')) is None


class TestQualifiersFilter:
    def test_qualifier_without_datatype_is_left_out_of_the_filter(self, wikibase, sparql_data):
        """A partial load can't put a qualifier without data type in the query: the statements aren't restricted by it."""
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType, cache=False)
        claim = ExternalID(value='P40095', prop_nr='P352', qualifiers=[Item(value='Q42', prop_nr='P642')])
        claim.qualifiers.add(Snak(property_number='P1545', datavalue={'value': '1', 'type': 'string'}))
        sparql_data.statement('Q99', 'P352', literal('P40095'), PTYPE_EXTERNAL_ID)

        frc.load_statements(claims=claim)

        [query] = load_statements_queries(wikibase)
        assert f'?sid <{wikibase.base_url}/prop/qualifier/P642> <{wikibase.base_url}/entity/Q42>.' in query
        assert '/prop/qualifier/P1545>' not in query
        assert len(frc.data['P352']['"P40095"']) == 1


class TestBaseFilterForms:
    def test_valueless_filter_shadowed_by_a_valued_one(self, wikibase):
        """A property filtered by a value and without one: the filter without value adds nothing (no ?zz variable)."""
        frc = wbi_fastrun.FastRunContainer(base_data_type=BaseDataType, base_filter=[Item(value='Q5', prop_nr='P31'), BaseDataType(prop_nr='P31')])

        assert frc._base_filter_string() == f'?entity <{wikibase.base_url}/prop/direct/P31> <{wikibase.base_url}/entity/Q5> .\n'

    def test_path_filter_without_value(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_data_type=BaseDataType, base_filter=[[Item(prop_nr='P31'), Item(prop_nr='P279')]])

        assert frc._base_filter_string() == f'?entity <{wikibase.base_url}/prop/direct/P31>/<{wikibase.base_url}/prop/direct/P279>* ?zzP31P279 .\n'

    def test_custom_wikibase_url(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_data_type=BaseDataType, base_filter=[Item(value='Q5', prop_nr='P31')])

        assert frc._base_filter_string(wb_url='https://other.example.org') == '?entity <https://other.example.org/prop/direct/P31> <https://other.example.org/entity/Q5> .\n'

    @pytest.mark.parametrize('base_filter', [['P31'], [[Item(prop_nr='P31')]], [[Item(prop_nr='P31'), 'P279']]])
    def test_invalid_base_filter_set_after_creation(self, wikibase, sparql_data, frc, base_filter):
        """base_filter is a public attribute: an invalid filter set after the creation is refused before any query."""
        frc.base_filter = base_filter

        with pytest.raises(ValueError, match='base_filter must be an instance of BaseDataType or a list of instances of BaseDataType'):
            frc._base_filter_string()
        with pytest.raises(ValueError, match='base_filter must be an instance of BaseDataType'):
            frc.load_statements(claims=ExternalID(value='P40095', prop_nr='P352'))
        assert not wikibase.sparql_queries


class TestLanguageDataEdgeCases:
    def test_entity_without_label_in_the_language(self, wikibase, sparql_data, frc):
        """The OPTIONAL of the query leaves ?label unbound for an entity without label in the language."""
        sparql_data.label('Q582', 'Villeurbanne', 'fr')
        sparql_data.labels.append({'entity': uri(f'{wikibase.base_url}/entity/Q583')})

        frc.init_language_data('fr', 'label')

        assert dict(frc.loaded_langs['fr']['label']) == {'Q582': {'Villeurbanne'}}
        assert frc.get_language_data('Q583', 'fr', 'label') == ['']
        assert frc.check_language_data('Q583', ['Lyon'], 'fr', 'label') is True

    def test_process_lang(self):
        data = wbi_fastrun.FastRunContainer._process_lang([
            {'entity': uri('https://wikibase.example.org/entity/Q1'), 'label': literal('a', lang='fr')},
            {'entity': uri('https://wikibase.example.org/entity/Q1'), 'label': literal('b', lang='fr')},
            {'entity': uri('https://wikibase.example.org/entity/Q2')},
        ])

        assert dict(data) == {'Q1': {'a', 'b'}}

    def test_no_bindings(self, wikibase, sparql_data, frc):
        """
        Without bindings (a response holding "bindings": null, which no compliant endpoint returns), nothing is stored,
        and the next call queries the endpoint again.
        """
        sparql_data.labels = None

        frc.init_language_data('fr', 'label')
        assert frc.loaded_langs == {'fr': {}}

        frc.init_language_data('fr', 'label')
        assert len(wikibase.sparql_queries) == 2

    def test_another_kind_of_language_data_of_a_loaded_language(self, wikibase, sparql_data, frc):
        sparql_data.label('Q582', 'Villeurbanne', 'fr')

        frc.init_language_data('fr', 'label')
        frc.init_language_data('fr', 'description')

        assert set(frc.loaded_langs['fr']) == {'label', 'description'}
        assert 'schema:description' in wikibase.sparql_queries[-1]


class TestFastrunStoreEdgeCases:
    def test_no_base_filter(self, wikibase):
        """A None base filter is taken as an empty filter, and the container is reused like any other."""
        frc = wbi_fastrun.get_fastrun_container(base_filter=None)

        assert frc.base_filter == []
        assert frc._base_filter_string() == ''
        assert wbi_fastrun.get_fastrun_container(base_filter=[]) is frc
        assert wbi_fastrun.fastrun_store == [frc]

    def test_reused_container_takes_the_new_cache_setting(self, wikibase):
        frc = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])
        assert frc.cache is True

        assert wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')], cache=False) is frc
        assert frc.cache is False

    def test_another_sparql_endpoint_creates_a_new_container(self, wikibase, preserve_config):
        frc = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])
        preserve_config['SPARQL_ENDPOINT_URL'] = 'https://other.example.org/sparql'

        other = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P352')])

        assert other is not frc
        assert other.sparql_endpoint_url == 'https://other.example.org/sparql'


class TestRepr:
    def test_repr(self, frc):
        text = repr(frc)

        assert text.startswith('<FastRunContainer @')
        assert "sparql_endpoint_url='" in text
        assert 'case_insensitive=False' in text


class TestCaseInsensitivePartialLoad:
    def test_case_insensitive_always_loads_the_complete_data(self, wikibase, sparql_data):
        """The SPARQL comparison is case sensitive: without cache, the case insensitive mode still loads every statement."""
        sparql_data.statement('Q99', 'P1', literal('FooBar'), PTYPE_STRING)
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P1')], base_data_type=BaseDataType, cache=False, case_insensitive=True)

        assert frc.write_required(claims=[String(value='FOOBAR', prop_nr='P1')]) is False

        [query] = load_statements_queries(wikibase)
        assert '"FOOBAR"' not in query
        assert 'P1' in frc.loaded_complete
