"""
Tests for the fastrun container. The SPARQL endpoint and the property
datatype lookups are served by the simulated Wikibase instance, so the whole
pipeline (query -> reverse lookup -> statement reconstruction -> comparison)
runs offline and deterministically.
"""
from collections import defaultdict
from typing import Any

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, ExternalID, Item
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.wbi_enums import ActionIfExists

from .conftest import literal, load_fixture, uri

wbi = WikibaseIntegrator()


def statement_bindings(wikibase, item_qid: str, prop_nr: str, values: list[dict], refs: dict | None = None) -> list[dict]:
    """Build SPARQL bindings shaped like the ones of wbi_fastrun._query_data."""
    bindings = []
    for index, value in enumerate(values):
        binding = {
            'sid': uri(f'{wikibase.base_url}/entity/statement/{item_qid}-{prop_nr}-{index}'),
            'item': uri(f'{wikibase.base_url}/entity/{item_qid}'),
            'v': value,
        }
        if refs:
            for ref_prop, ref_value in refs.items():
                bindings.append({
                    **binding,
                    'ref': uri(f'{wikibase.base_url}/reference/deadbeef{index}'),
                    'pr': uri(f'{wikibase.base_url}/prop/reference/{ref_prop}'),
                    'rval': ref_value,
                })
        else:
            bindings.append(binding)
    return bindings


class TestQueryData:
    def test_query_data(self, wikibase):
        """The container must query the SPARQL endpoint and store the data in its internal format."""
        wikibase.add_property('P352', 'external-id')

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)

        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q99', 'P352', [literal('P40095')])
        frc._query_data('P352')

        assert 'Q99' in frc.prop_data
        assert 'P352' in frc.prop_data['Q99']

        statement_id = list(frc.prop_data['Q99']['P352'].keys())[0]
        statement_data = frc.prop_data['Q99']['P352'][statement_id]
        assert all(key in statement_data for key in ('qual', 'ref', 'v'))
        assert statement_data['v'] == '"P40095"'
        assert frc.rev_lookup['"P40095"'] == {'Q99'}

    def test_query_data_item_and_uri_values(self, wikibase):
        wikibase.add_property('P828', 'wikibase-item')
        wikibase.add_property('P2888', 'url')

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P828')], base_data_type=BaseDataType)

        # wikibase-item value: the entity URI is reduced to its ID
        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q99', 'P828', [uri(f'{wikibase.base_url}/entity/Q18228398')])
        frc._query_data('P828')
        assert list(frc.prop_data['Q99']['P828'].values())[0]['v'] == 'Q18228398'

        # url value: kept as an URI
        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q99', 'P2888', [uri('http://purl.obolibrary.org/obo/DOID_1432')])
        frc._query_data('P2888')
        values = {statement['v'] for statement in frc.prop_data['Q99']['P2888'].values()}
        assert all(value.startswith('<http') for value in values)

    def test_query_data_ref(self, wikibase):
        wikibase.add_property('P352', 'external-id')
        wikibase.add_property('P248', 'wikibase-item')

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType, use_refs=True)

        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q99', 'P352', [literal('P40095')], refs={'P248': uri(f'{wikibase.base_url}/entity/Q1234')})
        frc._query_data('P352')

        statement_id = list(frc.prop_data['Q99']['P352'].keys())[0]
        statement_data = frc.prop_data['Q99']['P352'][statement_id]
        assert len(statement_data['ref']) == 1
        reference = list(statement_data['ref'].values())[0]
        assert ('P248', 'Q1234') in reference


class TestWriteRequiredEndToEnd:
    """Full fastrun pipeline: SPARQL query, reconstruction and comparison."""

    @pytest.fixture
    def frc(self, wikibase):
        # According to the SPARQL endpoint, Q582 already holds P352 = 'P40095'.
        wikibase.add_property('P352', 'external-id')
        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q582', 'P352', [literal('P40095')])
        return wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q27510868')], base_data_type=BaseDataType)

    def test_write_not_required_when_data_matches(self, frc):
        assert frc.write_required(data=[ExternalID(value='P40095', prop_nr='P352')]) is False

    def test_write_required_when_value_differs(self, frc):
        assert frc.write_required(data=[ExternalID(value='DIFFERENT', prop_nr='P352')]) is True

    def test_write_required_via_entity(self, wikibase, frc, item_q582):
        """BaseEntity.write_required goes through the shared fastrun store."""
        wbi_fastrun.fastrun_store.append(frc)

        item = ItemEntity().from_json(load_fixture('item_Q582'))
        item.claims.add(ExternalID(value='P40095', prop_nr='P352'))
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q27510868')]) is False

        item.claims.add(ExternalID(value='CHANGED', prop_nr='P352'))
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q27510868')]) is True

    def test_write_required_with_property_path_base_filter(self, wikibase, item_q582):
        """
        A property-path base_filter (a list of BaseDataType) must still select the matching claims.

        Regression: the anchor property (here P352) was never matched, so a write was always wrongly reported.
        """
        wikibase.add_property('P352', 'external-id')
        wikibase.add_property('P703', 'wikibase-item')
        wikibase.sparql_bindings = statement_bindings(wikibase, 'Q582', 'P352', [literal('P40095')])

        base_filter = [[BaseDataType(prop_nr='P352'), BaseDataType(prop_nr='P703')]]
        wbi_fastrun.fastrun_store.append(wbi_fastrun.FastRunContainer(base_filter=base_filter, base_data_type=BaseDataType))

        item = ItemEntity().from_json(load_fixture('item_Q582'))
        item.claims.add(ExternalID(value='P40095', prop_nr='P352'))
        assert item.write_required(base_filter=base_filter) is False

        item.claims.add(ExternalID(value='CHANGED', prop_nr='P352'))
        assert item.write_required(base_filter=base_filter) is True


class TestPropDatatype:
    def test_get_prop_datatype_is_cached(self, wikibase):
        wikibase.add_property('P352', 'external-id')
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)

        assert frc.get_prop_datatype('P352') == 'external-id'
        calls = len([r for r in wikibase.requests if r.get('action') == 'wbgetentities'])

        # A second lookup must be served from the per-instance cache, without any additional API request
        assert frc.get_prop_datatype('P352') == 'external-id'
        assert len([r for r in wikibase.requests if r.get('action') == 'wbgetentities']) == calls

        # clear() invalidates the cache
        frc.clear()
        assert 'P352' not in frc.prop_dt_map


class TestLanguageData:
    def test_language_data_and_check(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)

        wikibase.sparql_bindings = [
            {'item': uri(f'{wikibase.base_url}/entity/Q99'), 'label': literal('Earth', lang='en')},
        ]

        assert list(frc.get_language_data('Q99', 'en', 'label')) == ['Earth']
        # Same language data: no write required
        assert frc.check_language_data('Q99', ['Earth'], 'en', 'label') is False
        # Different language data: write required
        assert frc.check_language_data('Q99', ['not the Earth'], 'en', 'label') is True

    def test_empty_language_data(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352')], base_data_type=BaseDataType)
        wikibase.sparql_bindings = []

        assert frc.get_language_data('Q99', 'ak', 'label') == ['']
        assert frc.get_language_data('Q99', 'ak', 'description') == ['']
        assert frc.get_language_data('Q99', 'ak', 'aliases') == []
        assert frc.check_language_data('Q99', [''], 'ak', 'description') is False
        assert frc.check_language_data('Q99', [], 'ak', 'aliases') is False


class TestFastrunStore:
    def test_container_is_reused(self, wikibase):
        base_filter = [BaseDataType(prop_nr='P352')]
        first = wbi_fastrun.get_fastrun_container(base_filter=base_filter)
        second = wbi_fastrun.get_fastrun_container(base_filter=base_filter)
        assert first is second

    def test_different_parameters_create_new_container(self, wikibase):
        base_filter = [BaseDataType(prop_nr='P352')]
        first = wbi_fastrun.get_fastrun_container(base_filter=base_filter)
        second = wbi_fastrun.get_fastrun_container(base_filter=base_filter, use_refs=True)
        assert first is not second


class TestBaseFilters:
    def test_invalid_base_filter(self):
        with pytest.raises(ValueError):
            wbi_fastrun.FastRunContainer(base_filter=['not a datatype'], base_data_type=BaseDataType)

    def test_base_filter_string(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q27510868')], base_data_type=BaseDataType)
        assert f'?item <{wikibase.base_url}/prop/direct/P352> ?zzP352 .' in frc.base_filter_string
        assert f'?item <{wikibase.base_url}/prop/direct/P703>' in frc.base_filter_string


# --------------------------------------------------------------------- #
# Offline tests based on hand-crafted container contents. They validate
# the write_required comparison logic itself.
# --------------------------------------------------------------------- #

class FastRunContainerFakeQueryDataEnsembl(wbi_fastrun.FastRunContainer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.prop_dt_map = {'P248': 'wikibase-item', 'P594': 'external-id'}
        self.prop_data['Q14911732'] = {'P594': {
            'fake statement id': {
                'qual': set(),
                'ref': {'fake ref id': {
                    ('P248', 'Q106833387'),
                    ('P594', 'ENSG00000123374')}},
                'unit': '1',
                'v': '"ENSG00000123374"'}}}
        self.rev_lookup = defaultdict(set)
        self.rev_lookup['"ENSG00000123374"'].add('Q14911732')


class FastRunContainerFakeQueryDataEnsemblNoRef(wbi_fastrun.FastRunContainer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.prop_dt_map = {'P248': 'wikibase-item', 'P594': 'external-id'}
        self.prop_data['Q14911732'] = {'P594': {
            'fake statement id': {
                'qual': set(),
                'ref': {},
                'v': 'ENSG00000123374'}}}
        self.rev_lookup = defaultdict(set)
        self.rev_lookup['"ENSG00000123374"'].add('Q14911732')


def test_fastrun_ref_ensembl():
    # fastrun checks refs
    frc = FastRunContainerFakeQueryDataEnsembl(base_filter=[BaseDataType(prop_nr='P594'), Item(prop_nr='P703', value='Q15978631')], base_data_type=BaseDataType, use_refs=True)

    # statement has no ref
    statements = [ExternalID(value='ENSG00000123374', prop_nr='P594')]
    assert frc.write_required(data=statements)

    # statement has the same ref
    statements = [ExternalID(value='ENSG00000123374', prop_nr='P594', references=[[Item('Q106833387', prop_nr='P248'), ExternalID('ENSG00000123374', prop_nr='P594')]])]
    assert not frc.write_required(data=statements)

    # new statement has a different stated in
    statements = [ExternalID(value='ENSG00000123374', prop_nr='P594', references=[[Item('Q99999999999', prop_nr='P248'), ExternalID('ENSG00000123374', prop_nr='P594')]])]
    assert frc.write_required(data=statements)

    # fastrun doesn't check references, statement has no reference
    frc = FastRunContainerFakeQueryDataEnsemblNoRef(base_filter=[BaseDataType(prop_nr='P594'), Item(prop_nr='P703', value='Q15978631')], base_data_type=BaseDataType,
                                                    use_refs=False)
    statements = [ExternalID(value='ENSG00000123374', prop_nr='P594')]
    assert not frc.write_required(data=statements)

    # fastrun doesn't check references, statement has a reference
    frc = FastRunContainerFakeQueryDataEnsemblNoRef(base_filter=[BaseDataType(prop_nr='P594'), Item(prop_nr='P703', value='Q15978631')], base_data_type=BaseDataType,
                                                    use_refs=False)
    statements = [ExternalID(value='ENSG00000123374', prop_nr='P594', references=[[Item('Q123', prop_nr='P31')]])]
    assert not frc.write_required(data=statements)


class FakeQueryDataAppendProps(wbi_fastrun.FastRunContainer):
    # an item with three values for the same property
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.prop_dt_map = {'P527': 'wikibase-item', 'P248': 'wikibase-item', 'P594': 'external-id'}

        self.rev_lookup = defaultdict(set)
        self.rev_lookup['Q24784025'].add('Q3402672')
        self.rev_lookup['Q24743729'].add('Q3402672')
        self.rev_lookup['Q24782625'].add('Q3402672')

        self.prop_data['Q3402672'] = {'P527': {
            'Q3402672-11BA231B-857B-498B-AC4F-91D71EE007FD': {'qual': set(),
                                                              'ref': {
                                                                  '149c9c7ba4e246d9f09ce3ed0cdf7aa721aad5c8': {
                                                                      ('P248', 'Q3047275'),
                                                                  }},
                                                              'v': 'Q24784025'},
            'Q3402672-15F54AFF-7DCC-4DF6-A32F-73C48619B0B2': {'qual': set(),
                                                              'ref': {
                                                                  '149c9c7ba4e246d9f09ce3ed0cdf7aa721aad5c8': {
                                                                      ('P248', 'Q3047275'),
                                                                  }},
                                                              'v': 'Q24743729'},
            'Q3402672-C8F11D55-1B11-44E5-9EAF-637E062825A4': {'qual': set(),
                                                              'ref': {
                                                                  '149c9c7ba4e246d9f09ce3ed0cdf7aa721aad5c8': {
                                                                      ('P248', 'Q3047275')}},
                                                              'v': 'Q24782625'}}}


def test_append_props():
    qid = 'Q3402672'

    # don't consider refs
    frc = FakeQueryDataAppendProps(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q15978631')], base_data_type=BaseDataType)
    # with append
    statements = [Item(value='Q24784025', prop_nr='P527')]
    assert frc.write_required(data=statements, action_if_exists=ActionIfExists.APPEND_OR_REPLACE, cqid=qid) is False
    # with force append
    statements = [Item(value='Q24784025', prop_nr='P527')]
    assert frc.write_required(data=statements, action_if_exists=ActionIfExists.FORCE_APPEND, cqid=qid) is True
    # without append
    statements = [Item(value='Q24784025', prop_nr='P527')]
    assert frc.write_required(data=statements, cqid=qid) is True

    # if we are in append mode, and the refs are different, we should write
    frc = FakeQueryDataAppendProps(base_filter=[BaseDataType(prop_nr='P352'), Item(prop_nr='P703', value='Q15978631')], base_data_type=BaseDataType, use_refs=True)
    # with append
    statements = [Item(value='Q24784025', prop_nr='P527')]
    assert frc.write_required(data=statements, cqid=qid, action_if_exists=ActionIfExists.APPEND_OR_REPLACE) is True
    # without append
    statements = [Item(value='Q24784025', prop_nr='P527')]
    assert frc.write_required(data=statements, cqid=qid) is True
