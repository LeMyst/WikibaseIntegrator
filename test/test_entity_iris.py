"""
The bare entity IDs given as the unit of a Quantity (unit='Q11573') are completed with the Wikibase URL when the value is
serialized: the one of the WikibaseIntegrator instance of the entity, else wbi_config's (#1193). The calendar models and the
globes are entities of Wikidata on every instance.
"""
import json
import warnings

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, GlobeCoordinate, Quantity, String, Time
from wikibaseintegrator.models import Claims, Form, Qualifiers, Reference, References, Snak
from wikibaseintegrator.models.snak import _resolve_datavalue, _same_datavalue, _same_entity_iri, _serializing_for
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseSnakType
from wikibaseintegrator.wbi_helpers import format2wbi

from .conftest import MockWikibase, literal
from .test_wbi_fastrun import PTYPE_QUANTITY, XSD_DECIMAL, SparqlData

WIKIDATA = 'http://www.wikidata.org'
JULIAN = 'http://www.wikidata.org/entity/Q1985786'
MARS = 'Q111'


@pytest.fixture
def other(requests_mock, wikibase):
    """A second instance, while wbi_config points to the first one (wikibase)."""
    return MockWikibase(requests_mock, base_url='https://other.example.org')


@pytest.fixture
def wbi_other(other):
    return WikibaseIntegrator(config={'MEDIAWIKI_API_URL': other.mediawiki_api_url, 'SPARQL_ENDPOINT_URL': other.sparql_endpoint_url, 'WIKIBASE_URL': other.base_url})


def unit(claim_json):
    return claim_json['mainsnak']['datavalue']['value']['unit']


class TestDatatypes:
    def test_a_unit_id_is_kept_and_completed_when_serialized(self, wikibase):
        claim = Quantity(amount=12, unit='Q11573', prop_nr='P1')
        assert claim.mainsnak.datavalue['value']['unit'] == 'Q11573'
        assert unit(claim.get_json()) == f'{wikibase.base_url}/entity/Q11573'

        # Read when serialized
        wbi_config['WIKIBASE_URL'] = 'https://changed.example.org'
        assert unit(claim.get_json()) == 'https://changed.example.org/entity/Q11573'
        # The datavalue isn't changed
        assert claim.mainsnak.datavalue['value']['unit'] == 'Q11573'

        # With a Wikibase URL, the IRI is built at once, as before
        assert Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=WIKIDATA).mainsnak.datavalue['value']['unit'] == f'{WIKIDATA}/entity/Q11573'

    def test_the_iris_are_kept(self, wikibase):
        claim = Quantity(amount=12, unit=f'{WIKIDATA}/entity/Q11573', prop_nr='P1')
        assert claim.get_json()['mainsnak']['datavalue'] is claim.mainsnak.datavalue
        assert unit(Quantity(amount=12, prop_nr='P1').get_json()) == '1'


class TestCalendarModelsAndGlobes:
    """Wikibase only accepts the calendar models and the globes of Wikidata, on every instance (ValidatorBuilders::$wikidataBaseUri)."""

    @pytest.mark.parametrize('wikibase_url', ['https://other.example.org', WIKIDATA])
    def test_an_id_is_an_entity_of_wikidata_on_every_instance(self, wikibase, wikibase_url):
        wbi_config['WIKIBASE_URL'] = wikibase_url
        assert Time(time='+2020-01-01T00:00:00Z', calendarmodel='Q1985786', prop_nr='P1').mainsnak.datavalue['value']['calendarmodel'] == JULIAN
        assert GlobeCoordinate(latitude=1, longitude=2, globe=MARS, prop_nr='P1').mainsnak.datavalue['value']['globe'] == f'{WIKIDATA}/entity/{MARS}'

    def test_in_an_entity_of_another_instance(self, other, wbi_other):
        item = wbi_other.item.new()
        item.claims.add([Time(time='+1500-01-01T00:00:00Z', calendarmodel='Q1985786', prop_nr='P1'), GlobeCoordinate(latitude=1, longitude=2, globe=MARS, prop_nr='P2')])
        claims = item.get_json()['claims']
        assert claims['P1'][0]['mainsnak']['datavalue']['value']['calendarmodel'] == JULIAN
        assert claims['P2'][0]['mainsnak']['datavalue']['value']['globe'] == f'{WIKIDATA}/entity/{MARS}'

    def test_the_defaults(self, wikibase):
        assert Time(time='+2020-01-01T00:00:00Z', prop_nr='P1').mainsnak.datavalue['value']['calendarmodel'] == wbi_config['CALENDAR_MODEL_QID']
        assert GlobeCoordinate(latitude=1, longitude=2, prop_nr='P1').mainsnak.datavalue['value']['globe'] == wbi_config['COORDINATE_GLOBE_QID']

        wbi_config['CALENDAR_MODEL_QID'] = 'Q1985786'
        wbi_config['COORDINATE_GLOBE_QID'] = 'Q2'
        wbi_config['WIKIBASE_URL'] = 'https://other.example.org'
        assert Time(time='+2020-01-01T00:00:00Z', prop_nr='P1').mainsnak.datavalue['value']['calendarmodel'] == JULIAN
        # Q2 is the Earth, on every instance
        with pytest.raises(ValueError, match='latitude must be between -90 and 90'):
            GlobeCoordinate(latitude=100, longitude=2, prop_nr='P1')
        with pytest.raises(ValueError, match='latitude must be between -90 and 90'):
            GlobeCoordinate(latitude=100, longitude=2, globe='Q2', prop_nr='P1')
        assert GlobeCoordinate(latitude=100, longitude=2, globe=MARS, prop_nr='P1').mainsnak.datavalue['value']['latitude'] == 100

    def test_wikibase_url_is_deprecated_and_ignored(self, wikibase):
        with pytest.warns(DeprecationWarning, match=r"The wikibase_url argument of Time is deprecated .* \(http://www.wikidata.org/entity/Q1985786\)") as record:
            time = Time(time='+2020-01-01T00:00:00Z', calendarmodel='Q1985786', wikibase_url='https://other.example.org', prop_nr='P1')
        assert time.mainsnak.datavalue['value']['calendarmodel'] == JULIAN
        assert record[0].filename == __file__
        with pytest.warns(DeprecationWarning, match='The wikibase_url argument of Time is deprecated'):
            time.set_value(time='+2020-01-01T00:00:00Z', wikibase_url='https://other.example.org')

        with pytest.warns(DeprecationWarning, match='The wikibase_url argument of GlobeCoordinate is deprecated') as record:
            globe = GlobeCoordinate(latitude=1, longitude=2, globe=MARS, wikibase_url='https://other.example.org', prop_nr='P1')
        assert globe.mainsnak.datavalue['value']['globe'] == f'{WIKIDATA}/entity/{MARS}'
        assert record[0].filename == __file__
        with pytest.warns(DeprecationWarning, match='The wikibase_url argument of GlobeCoordinate is deprecated'):
            globe.set_value(latitude=1, longitude=2, wikibase_url='https://other.example.org')

    def test_format2wbi_doesnt_warn(self, wikibase):
        wikibase.add_property('P1', 'time')
        wikibase.add_property('P2', 'globe-coordinate')
        with warnings.catch_warnings():
            warnings.simplefilter('error', DeprecationWarning)
            warnings.filterwarnings('ignore', message='format2wbi.. is experimental')
            item = format2wbi('item', json.dumps({'claims': {'P1': {'time': '+2020-01-01T00:00:00Z', 'calendarmodel': 'Q1985786'},
                                                             'P2': {'latitude': 1, 'longitude': 2, 'globe': MARS}}}), wikibase_url='https://other.example.org')
        assert item.claims.get('P1')[0].mainsnak.datavalue['value']['calendarmodel'] == JULIAN
        assert item.claims.get('P2')[0].mainsnak.datavalue['value']['globe'] == f'{WIKIDATA}/entity/{MARS}'


class TestEntities:
    def test_an_entity_uses_the_wikibase_url_of_its_instance(self, wikibase, other, wbi_other):
        item = wbi_other.item.new()
        item.claims.add(Quantity(amount=12, unit='Q11573', prop_nr='P1',
                                 qualifiers=[Quantity(amount=1, unit='Q11574', prop_nr='P2')], references=[[Quantity(amount=2, unit='Q11575', prop_nr='P3')]]))
        claim_json = item.get_json()['claims']['P1'][0]

        assert unit(claim_json) == f'{other.base_url}/entity/Q11573'
        assert claim_json['qualifiers']['P2'][0]['datavalue']['value']['unit'] == f'{other.base_url}/entity/Q11574'
        assert claim_json['references'][0]['snaks']['P3'][0]['datavalue']['value']['unit'] == f'{other.base_url}/entity/Q11575'
        # Out of the entity, wbi_config's
        assert unit(item.claims.get('P1')[0].get_json()) == f'{wikibase.base_url}/entity/Q11573'

    def test_write(self, wikibase, other, wbi_other):
        item = wbi_other.item.new()
        item.claims.add(Quantity(amount=12, unit='Q11573', prop_nr='P1'))
        written = item.write(allow_anonymous=True)

        assert unit(other.edits[0]['data']['claims']['P1'][0]) == f'{other.base_url}/entity/Q11573'
        assert written.claims.get('P1')[0].mainsnak.datavalue['value']['unit'] == f'{other.base_url}/entity/Q11573'

    def test_the_default_instance(self, wikibase):
        item = WikibaseIntegrator().item.new()
        item.claims.add(Quantity(amount=12, unit='Q11573', prop_nr='P1'))
        assert unit(item.get_json()['claims']['P1'][0]) == f'{wikibase.base_url}/entity/Q11573'

    def test_lexeme_forms_and_senses(self, other, wbi_other):
        other.add_fixture('lexeme_L5')
        lexeme = wbi_other.lexeme.get('L5')
        form = Form()
        form.representations.set(language='en', value='others')
        form.claims.add(Quantity(amount=12, unit='Q11573', prop_nr='P1'))
        lexeme.forms.add(form)
        assert unit(lexeme.get_json()['forms'][-1]['claims']['P1'][0]) == f'{other.base_url}/entity/Q11573'

        lexeme.write_form(form, allow_anonymous=True)
        assert unit(json.loads(other.requests[-1]['data'])['claims']['P1'][0]) == f'{other.base_url}/entity/Q11573'

        sense = lexeme.senses.senses[0]
        sense.claims.add(Quantity(amount=3, unit='Q11576', prop_nr='P1'))
        lexeme.edit_sense(sense, allow_anonymous=True)
        assert unit(json.loads(next(request for request in other.requests if request['action'] == 'wbleditsenseelements')['data'])['claims']['P1'][0]) \
            == f'{other.base_url}/entity/Q11576'

    def test_the_serialization_context_is_restored(self, wikibase):
        claim = Quantity(amount=12, unit='Q11573', prop_nr='P1')
        with _serializing_for('https://inner.example.org'):
            assert unit(claim.get_json()) == 'https://inner.example.org/entity/Q11573'
        assert unit(claim.get_json()) == f'{wikibase.base_url}/entity/Q11573'


class TestCopies:
    def test_a_claim_added_as_a_qualifier_or_a_reference_keeps_the_id(self, wikibase):
        claim = Quantity(amount=12, unit='Q11573', prop_nr='P1')

        assert next(iter(Qualifiers().add(claim))).datavalue['value']['unit'] == 'Q11573'
        assert next(iter(Qualifiers().set([claim]))).datavalue['value']['unit'] == 'Q11573'
        assert next(iter(Reference().add(claim))).datavalue['value']['unit'] == 'Q11573'
        references = References().add(claim)
        assert next(iter(next(iter(references)))).datavalue['value']['unit'] == 'Q11573'
        references.remove(claim)
        assert len(references) == 0

        for references_argument in ([claim], [[claim]]):
            holder = String(prop_nr='P2', value='x', references=references_argument)
            assert [next(iter(reference)).datavalue['value']['unit'] for reference in holder.references] == ['Q11573']


class TestEquality:
    def test_an_id_equals_its_iri_on_any_instance(self, wikibase, other):
        bare = Quantity(amount=12, unit='Q11573', prop_nr='P1')
        assert bare == Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=other.base_url)
        assert Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=other.base_url) == bare
        assert bare.mainsnak == Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=WIKIDATA).mainsnak

    def test_different_values(self, wikibase, other):
        bare = Quantity(amount=12, unit='Q11573', prop_nr='P1')
        assert bare != Quantity(amount=12, unit='Q11574', prop_nr='P1', wikibase_url=other.base_url)
        assert bare != Quantity(amount=13, unit='Q11573', prop_nr='P1', wikibase_url=other.base_url)
        # Two IRIs are compared as they are
        assert Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=WIKIDATA) != Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=other.base_url)

    def test_claims_add_doesnt_duplicate_a_read_claim(self, wikibase, other):
        claims = Claims().add(Quantity(amount=12, unit='Q11573', prop_nr='P1', wikibase_url=other.base_url))
        claims.add(Quantity(amount=12, unit='Q11573', prop_nr='P1'))
        assert len(claims) == 1

    def test_globe_coordinates(self, wikibase):
        assert GlobeCoordinate(latitude=1, longitude=2, globe=MARS, prop_nr='P1') == GlobeCoordinate(latitude=1, longitude=2, globe=f'{WIKIDATA}/entity/{MARS}',
                                                                                                    prop_nr='P1')
        assert GlobeCoordinate(latitude=1, longitude=2, globe=MARS, prop_nr='P1') != GlobeCoordinate(latitude=1, longitude=2, globe='Q112', prop_nr='P1')

    @pytest.mark.parametrize(('first', 'second', 'same'), [
        ({'type': 'quantity', 'value': {'amount': '+1', 'unit': 'Q1'}}, {'type': 'quantity', 'value': {'amount': '+1', 'unit': 'http://x/entity/Q1'}}, True),
        ({'type': 'quantity', 'value': {'amount': '+1', 'unit': 'http://x/entity/Q1'}}, {'type': 'quantity', 'value': {'amount': '+1', 'unit': 'Q1'}}, True),
        ({'type': 'quantity', 'value': {'amount': '+1', 'unit': 'Q1'}}, {'type': 'quantity', 'value': {'amount': '+1', 'unit': 'http://x/entity/Q10'}}, False),
        ({'type': 'quantity', 'value': {'amount': '+1', 'unit': 'http://x/entity/Q1'}}, {'type': 'quantity', 'value': {'amount': '+1', 'unit': 'http://y/entity/Q1'}}, False),
        ({'type': 'quantity', 'value': {'amount': '+1', 'unit': 'Q1'}}, {'type': 'string', 'value': 'Q1'}, False),
        ({'type': 'string', 'value': 'a'}, {'type': 'string', 'value': 'b'}, False),
        ({'type': 'quantity', 'value': 'Q1'}, {'type': 'quantity', 'value': {'unit': 'Q1'}}, False),
        ({'type': 'quantity', 'value': {'unit': 'Q1'}, 'extra': 1}, {'type': 'quantity', 'value': {'unit': 'http://x/entity/Q1'}}, False),
    ])
    def test_same_datavalue(self, first, second, same):
        assert _same_datavalue(first, second) is same

    def test_resolve_datavalue(self, wikibase):
        for datavalue in ({}, {'type': 'string', 'value': 'Q1'}, {'type': 'quantity', 'value': 'Q1'}, {'type': 'quantity', 'value': {'amount': '+1'}}):
            assert _resolve_datavalue(datavalue) is datavalue
        # Only the units: the calendar models and the globes are entities of Wikidata
        for datavalue in ({'type': 'time', 'value': {'calendarmodel': 'Q1985786'}}, {'type': 'globecoordinate', 'value': {'globe': 'Q2'}}):
            assert _resolve_datavalue(datavalue) is datavalue
        assert _resolve_datavalue({'type': 'quantity', 'value': {'unit': 'Q1'}}, wikibase_url=WIKIDATA) == {'type': 'quantity', 'value': {'unit': f'{WIKIDATA}/entity/Q1'}}

    def test_same_entity_iri(self):
        assert _same_entity_iri('Q1', 'Q1')
        assert _same_entity_iri(None, None)
        assert not _same_entity_iri('Q1', None)
        assert not _same_entity_iri('http://x/entity/Q1', 1)

    def test_time_without_calendar_model(self, wikibase):
        time = Time(prop_nr='P1').from_json({'mainsnak': {'snaktype': 'value', 'property': 'P1', 'datatype': 'time', 'datavalue': {
            'type': 'time', 'value': {'time': '+2020-01-01T00:00:00Z', 'precision': 11, 'timezone': 0, 'before': 0, 'after': 0}}}, 'type': 'statement', 'rank': 'normal'})
        assert time.get_sparql_value() == '"+2020-01-01T00:00:00Z"^^xsd:dateTime'

    def test_a_snak_without_value(self, wikibase):
        snak = Snak(snaktype=WikibaseSnakType.UNKNOWN_VALUE, property_number='P1')
        assert 'datavalue' not in snak.get_json()


class TestFastRun:
    def test_write_required_on_another_instance(self, wikibase, other, wbi_other):
        other.add_property('P2046', 'quantity')
        SparqlData(other).statement('Q99', 'P2046', literal('+42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit=f'{other.base_url}/entity/Q712226')

        item = wbi_other.item.new()
        item.id = 'Q99'
        item.claims.add(Quantity(amount=42, unit='Q712226', prop_nr='P2046'))
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P2046')]) is False

        item.claims.add(Quantity(amount=42, unit='Q11573', prop_nr='P2046'))
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P2046')]) is True
        # The claims of the entity keep their IDs
        assert [claim.mainsnak.datavalue['value']['unit'] for claim in item.claims] == ['Q712226', 'Q11573']

    def test_get_entities_and_load_statements(self, wikibase, other):
        SparqlData(other).statement('Q99', 'P2046', literal('+42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit=f'{other.base_url}/entity/Q712226')
        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P2046')], sparql_endpoint_url=other.sparql_endpoint_url, wikibase_url=other.base_url)

        claim = Quantity(amount=42, unit='Q712226', prop_nr='P2046')
        assert frc.get_entities(claims=claim) == ['Q99']
        frc.load_statements(claims=claim)
        assert 'P2046' in frc.data

    def test_the_claims_without_id_arent_copied(self):
        claims = [String(prop_nr='P1', value='a'), Quantity(amount=1, unit=f'{WIKIDATA}/entity/Q11573', prop_nr='P2')]
        assert all(resolved is claim for resolved, claim in zip(wbi_fastrun._with_entity_iris(claims, WIKIDATA), claims))
