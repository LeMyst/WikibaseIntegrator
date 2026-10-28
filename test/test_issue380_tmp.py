"""Temporary reproduction of issue #380: write_required() on an unchanged existing item."""
import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import URL, BaseDataType, ExternalID, GlobeCoordinate, Item, Quantity, String, Time
from wikibaseintegrator.models import Qualifiers

from .conftest import literal, uri
from .test_wbi_fastrun import PTYPE_EXTERNAL_ID, PTYPE_ITEM, PTYPE_QUANTITY, PTYPE_STRING, PTYPE_TIME, XSD_DATETIME, XSD_DECIMAL, SparqlData

wbi = WikibaseIntegrator()
PTYPE_URL = 'http://wikiba.se/ontology#Url'
PTYPE_GLOBE = 'http://wikiba.se/ontology#GlobeCoordinate'
WD = 'http://www.wikidata.org/entity/'


@pytest.fixture(autouse=True)
def clear_store():
    wbi_fastrun.fastrun_store.clear()
    yield
    wbi_fastrun.fastrun_store.clear()


@pytest.fixture
def sd(wikibase):
    return SparqlData(wikibase)


def mainsnaks(sd: SparqlData) -> list:
    """An existing item Q99 with one statement per common datatype, the SPARQL endpoint holding the same data."""
    sids = {
        'P1': sd.statement('Q99', 'P1', literal('a title'), PTYPE_STRING),
        'P2': sd.statement('Q99', 'P2', uri('https://example.org/page'), PTYPE_URL),
        'P3': sd.statement('Q99', 'P3', uri(f'{sd.wikibase.base_url}/entity/Q5'), PTYPE_ITEM),
        'P4': sd.statement('Q99', 'P4', literal('abc-123'), PTYPE_EXTERNAL_ID),
        'P5': sd.statement('Q99', 'P5', literal('2022-07-19T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME),
        'P6': sd.statement('Q99', 'P6', literal('42', datatype=XSD_DECIMAL), PTYPE_QUANTITY, unit='http://www.wikidata.org/entity/Q199'),
    }
    claims = [
        String(value='a title', prop_nr='P1'),
        URL(value='https://example.org/page', prop_nr='P2'),
        Item(value='Q5', prop_nr='P3'),
        ExternalID(value='abc-123', prop_nr='P4'),
        Time(time='+2022-07-19T00:00:00Z', precision=11, prop_nr='P5'),
        Quantity(amount=42, prop_nr='P6'),
    ]
    return [sids, claims]


def item_with(claims: list):
    item = wbi.item.new()
    item.id = 'Q99'
    for claim in claims:
        item.claims.add(claim)
    return item


def base_filter(props):
    return [BaseDataType(prop_nr=p) for p in props]


def test_unchanged_item_mainsnaks_only(wikibase, sd):
    _, claims = mainsnaks(sd)
    assert item_with(claims).write_required(base_filter=base_filter(['P1', 'P2', 'P3', 'P4', 'P5', 'P6'])) is False


def test_unchanged_item_changed_value_still_detected(wikibase, sd):
    _, claims = mainsnaks(sd)
    claims[0] = String(value='another title', prop_nr='P1')
    assert item_with(claims).write_required(base_filter=base_filter(['P1', 'P2', 'P3', 'P4', 'P5', 'P6'])) is True


@pytest.mark.parametrize('qualifier, binding, ptype', [
    (String(value='q', prop_nr='P10'), literal('q'), PTYPE_STRING),
    (Item(value='Q7', prop_nr='P10'), uri('ITEM'), PTYPE_ITEM),
    (Time(time='+2022-07-19T00:00:00Z', precision=11, prop_nr='P10'), literal('2022-07-19T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME),
    (Time(time='+2022-07-00T00:00:00Z', precision=10, prop_nr='P10'), literal('2022-07-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME),
    (Time(time='+2022-00-00T00:00:00Z', precision=9, prop_nr='P10'), literal('2022-01-01T00:00:00Z', datatype=XSD_DATETIME), PTYPE_TIME),
    (Quantity(amount=3, prop_nr='P10'), literal('3', datatype=XSD_DECIMAL), PTYPE_QUANTITY),
    (Quantity(amount=3, upper_bound=4, lower_bound=2, prop_nr='P10'), literal('3', datatype=XSD_DECIMAL), PTYPE_QUANTITY),
    (GlobeCoordinate(latitude=1.5, longitude=2.5, precision=0.01, prop_nr='P10'), literal('Point(2.5 1.5)', datatype='http://www.opengis.net/ont/geosparql#wktLiteral'), PTYPE_GLOBE),
], ids=['string', 'item', 'time-day', 'time-month', 'time-year', 'quantity', 'quantity-bounds', 'globe'])
def test_unchanged_item_with_qualifier(wikibase, sd, qualifier, binding, ptype):
    sids, claims = mainsnaks(sd)
    if binding['value'] == 'ITEM':
        binding = uri(f'{wikibase.base_url}/entity/Q7')
    sd.qualifier(sids['P1'], 'P10', binding, ptype)
    claims[0] = String(value='a title', prop_nr='P1', qualifiers=Qualifiers().add(qualifier))
    assert item_with(claims).write_required(base_filter=base_filter(['P1', 'P2', 'P3', 'P4', 'P5', 'P6'])) is False


def test_base_filter_with_a_property_the_item_lacks(wikibase, sd):
    """The reporter's pattern: every property of the Wikibase in base_filter, including P50 that Q99 does not have."""
    _, claims = mainsnaks(sd)
    queries = []
    dispatch = sd.dispatch
    sd.wikibase.sparql_bindings = lambda q: (queries.append(q), dispatch(q))[1]
    item_with(claims).write_required(base_filter=base_filter(['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P50']))
    # The generated query requires ?entity to hold P50: on a real endpoint Q99 would never match
    assert any('/prop/direct/P50> ?zzP50' in q for q in queries)


@pytest.mark.parametrize('claim, binding', [
    (Time(time='+1987-00-00T00:00:00Z', precision=9, prop_nr='P5'), literal('1987-01-01T00:00:00Z', datatype=XSD_DATETIME)),
    (Time(time='+1987-05-00T00:00:00Z', precision=10, prop_nr='P5'), literal('1987-05-01T00:00:00Z', datatype=XSD_DATETIME)),
], ids=['year', 'month'])
def test_unchanged_mainsnak_low_precision_time(wikibase, sd, claim, binding):
    sd.statement('Q99', 'P5', binding, PTYPE_TIME)
    assert item_with([claim]).write_required(base_filter=base_filter(['P5'])) is False
