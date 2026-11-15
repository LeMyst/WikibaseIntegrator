"""
The fast run mode against a real query service (WDQS), kept up to date by its updater.

The unit tests check the SPARQL queries and the parsing of their results against canned responses. These tests check
them against the RDF that Wikibase exports and WDQS stores: one item with a claim of each common data type is written,
then compared with the same data built locally, which must need no write.
"""
import time
import uuid

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import URL, ExternalID, GlobeCoordinate, Item, MonolingualText, Quantity, String, Time
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseTimePrecision
from wikibaseintegrator.wbi_helpers import execute_sparql_query

pytestmark = pytest.mark.integration

RUN_ID = uuid.uuid4().hex[:10]

# How long to wait for the updater to load an edit into the query service, in seconds
QUERY_SERVICE_TIMEOUT = 180

GREGORIAN = 'http://www.wikidata.org/entity/Q1985727'
JULIAN = 'http://www.wikidata.org/entity/Q1985786'

DATATYPES = (WikibaseDatatype.STRING, WikibaseDatatype.EXTERNALID, WikibaseDatatype.ITEM, WikibaseDatatype.QUANTITY, WikibaseDatatype.TIME,
             WikibaseDatatype.MONOLINGUALTEXT, WikibaseDatatype.URL, WikibaseDatatype.GLOBECOORDINATE)


@pytest.fixture(autouse=True)
def empty_fastrun_store():
    """The fast run containers are cached by base filter for the whole process: each test starts from the query service."""
    wbi_fastrun.fastrun_store.clear()
    yield
    wbi_fastrun.fastrun_store.clear()


def wait_for_query_service(entity_id: str, prop_nr: str, value: str) -> None:
    """Wait until the query service holds the statement `prop_nr` = `value` (a SPARQL term) of `entity_id`."""
    wb_url = wbi_config['WIKIBASE_URL']
    query = f'ASK {{ <{wb_url}/entity/{entity_id}> <{wb_url}/prop/direct/{prop_nr}> {value} . }}'
    deadline = time.monotonic() + QUERY_SERVICE_TIMEOUT
    while not execute_sparql_query(query)['boolean']:
        if time.monotonic() > deadline:
            pytest.fail(f'The query service did not load {entity_id} within {QUERY_SERVICE_TIMEOUT} seconds')
        time.sleep(2)


@pytest.fixture(scope='module')
def properties(login, query_service):
    """A property of each data type, created for this test run."""
    wbi = WikibaseIntegrator(login=login)
    created = {}
    for datatype in DATATYPES:
        prop = wbi.property.new(datatype=datatype)
        prop.labels.set(language='en', value=f'WBI integration test fast run {datatype} {RUN_ID}')
        created[datatype] = prop.write(summary='WikibaseIntegrator integration test setup').id
    return created


@pytest.fixture(scope='module')
def target_item(login, query_service, delete_entities):
    """The value of the item claim."""
    wbi = WikibaseIntegrator(login=login)
    item = wbi.item.new()
    item.labels.set(language='en', value=f'WBI integration test fast run target {RUN_ID}')
    item_id = item.write(summary='WikibaseIntegrator integration test setup').id
    yield item_id
    delete_entities([item_id])


def build_claims(properties, target_item, string_value=f'fast run string {RUN_ID}'):
    return [
        String(prop_nr=properties[WikibaseDatatype.STRING], value=string_value),
        ExternalID(prop_nr=properties[WikibaseDatatype.EXTERNALID], value=f'id-{RUN_ID}'),
        Item(prop_nr=properties[WikibaseDatatype.ITEM], value=target_item),
        Quantity(prop_nr=properties[WikibaseDatatype.QUANTITY], amount='12.5', unit='1'),
        Time(prop_nr=properties[WikibaseDatatype.TIME], time='+2020-02-08T00:00:00Z', precision=WikibaseTimePrecision.DAY, calendarmodel=GREGORIAN),
        MonolingualText(prop_nr=properties[WikibaseDatatype.MONOLINGUALTEXT], text=f'fast run text {RUN_ID}', language='en'),
        URL(prop_nr=properties[WikibaseDatatype.URL], value=f'https://example.org/{RUN_ID}'),
        GlobeCoordinate(prop_nr=properties[WikibaseDatatype.GLOBECOORDINATE], latitude=48.8566, longitude=2.3522, precision=0.0001),
    ]


DATATYPE_CLASSES = {WikibaseDatatype.STRING: String, WikibaseDatatype.EXTERNALID: ExternalID, WikibaseDatatype.ITEM: Item, WikibaseDatatype.QUANTITY: Quantity,
                    WikibaseDatatype.TIME: Time, WikibaseDatatype.MONOLINGUALTEXT: MonolingualText, WikibaseDatatype.URL: URL,
                    WikibaseDatatype.GLOBECOORDINATE: GlobeCoordinate}


def base_filter(properties):
    """The entities with a claim of each property: every claim of build_claims() is compared."""
    return [DATATYPE_CLASSES[datatype](prop_nr=prop_nr) for datatype, prop_nr in properties.items()]


@pytest.fixture(scope='module')
def synced_item(login, properties, target_item, delete_entities):
    """The item holding build_claims(), once the query service has loaded it."""
    wbi = WikibaseIntegrator(login=login)
    item = wbi.item.new()
    item.labels.set(language='en', value=f'WBI integration test fast run item {RUN_ID}')
    item.claims.add(build_claims(properties, target_item))
    item = item.write(summary='WikibaseIntegrator integration test: fast run')
    wait_for_query_service(item.id, properties[WikibaseDatatype.EXTERNALID], f'"id-{RUN_ID}"')
    yield item
    delete_entities([item.id])


class TestWriteRequired:
    def test_the_same_data_needs_no_write(self, wbi, properties, target_item, synced_item):
        item = wbi.item.new()
        item.claims.add(build_claims(properties, target_item))
        assert not item.write_required(base_filter=base_filter(properties))

    def test_the_same_data_on_the_known_entity_needs_no_write(self, wbi, properties, target_item, synced_item):
        item = wbi.item.get(synced_item.id)
        item.claims.add(build_claims(properties, target_item))
        assert not item.write_required(base_filter=base_filter(properties))

    def test_a_changed_value_needs_a_write(self, wbi, properties, target_item, synced_item):
        item = wbi.item.new()
        item.claims.add(build_claims(properties, target_item, string_value=f'another string {RUN_ID}'))
        assert item.write_required(base_filter=base_filter(properties))

    def test_without_cache(self, wbi, properties, target_item, synced_item):
        item = wbi.item.new()
        item.claims.add(build_claims(properties, target_item))
        assert not item.write_required(base_filter=base_filter(properties), cache=False)


class TestFastRunContainer:
    def test_get_entities_finds_the_item_by_a_unique_value(self, properties, synced_item):
        frc = wbi_fastrun.get_fastrun_container(base_filter=[ExternalID(prop_nr=properties[WikibaseDatatype.EXTERNALID])])
        assert frc.get_entities(claims=[ExternalID(prop_nr=properties[WikibaseDatatype.EXTERNALID], value=f'id-{RUN_ID}')]) == [synced_item.id]

    def test_check_language_data(self, properties, synced_item):
        frc = wbi_fastrun.get_fastrun_container(base_filter=[ExternalID(prop_nr=properties[WikibaseDatatype.EXTERNALID])])
        label = f'WBI integration test fast run item {RUN_ID}'
        assert not frc.check_language_data(qid=synced_item.id, lang_data=[label], lang='en', lang_data_type='label')
        assert frc.check_language_data(qid=synced_item.id, lang_data=['another label'], lang='en', lang_data_type='label')


# The RDF export numbers the BCE years like XSD 1.1 (-0044 in JSON is -0043 in RDF) and converts the days of the
# Julian calendar to the Gregorian calendar, the calendar model is on the value node (#1197)
@pytest.mark.parametrize('time_value, precision, calendarmodel', [
    ('-0044-03-15T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN),
    ('-0100-00-00T00:00:00Z', WikibaseTimePrecision.YEAR, GREGORIAN),
    ('-0500-00-00T00:00:00Z', WikibaseTimePrecision.CENTURY, GREGORIAN),
    ('+1500-03-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN),
    ('-0044-03-15T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN),
    ('+1500-00-00T00:00:00Z', WikibaseTimePrecision.YEAR, JULIAN),
], ids=['bce-day', 'bce-year', 'bce-century', 'julian-day', 'julian-bce-day', 'julian-year'])
def test_dates_needing_a_conversion(wbi, properties, delete_entities, time_value, precision, calendarmodel):
    prop_nr = properties[WikibaseDatatype.TIME]
    unique = ExternalID(prop_nr=properties[WikibaseDatatype.EXTERNALID], value=f'date-{time_value}-{precision}-{calendarmodel[-7:]}-{RUN_ID}')

    def claims(calendar=calendarmodel):
        # The date as a statement, and as a qualifier
        return [ExternalID(prop_nr=unique.mainsnak.property_number, value=unique.mainsnak.datavalue['value'],
                           qualifiers=[Time(prop_nr=prop_nr, time=time_value, precision=precision, calendarmodel=calendar)]),
                Time(prop_nr=prop_nr, time=time_value, precision=precision, calendarmodel=calendar)]

    item = wbi.item.new()
    item.claims.add(claims())
    item_id = item.write(summary='WikibaseIntegrator integration test: fast run dates').id
    try:
        wait_for_query_service(item_id, unique.mainsnak.property_number, f'"{unique.mainsnak.datavalue["value"]}"')
        base_filter = [ExternalID(prop_nr=unique.mainsnak.property_number), Time(prop_nr=prop_nr)]

        local = wbi.item.new()
        local.claims.add(claims())
        assert not local.write_required(base_filter=base_filter)

        # The same timestamp in the other calendar is another value
        other = wbi.item.new()
        other.claims.add(claims(calendar=GREGORIAN if calendarmodel == JULIAN else JULIAN))
        assert other.write_required(base_filter=base_filter)
    finally:
        delete_entities([item_id])


def test_instance_configuration(login, properties, target_item, synced_item, integration_config, monkeypatch):
    """A WikibaseIntegrator configured for the instance works while wbi_config points elsewhere (#1193)."""
    instance = {key: integration_config[key] for key in ('MEDIAWIKI_API_URL', 'SPARQL_ENDPOINT_URL', 'WIKIBASE_URL', 'USER_AGENT')}
    for key, url in (('MEDIAWIKI_API_URL', 'http://wbi-unreachable.invalid/w/api.php'), ('SPARQL_ENDPOINT_URL', 'http://wbi-unreachable.invalid/sparql'),
                     ('WIKIBASE_URL', 'http://wbi-unreachable.invalid')):
        monkeypatch.setitem(wbi_config, key, url)
    wbi = WikibaseIntegrator(login=login, config=instance)

    # Read, and fast run against the query service of the instance
    item = wbi.item.get(synced_item.id)
    assert item.get_entity_url() == f"{instance['WIKIBASE_URL']}/entity/{synced_item.id}"
    item.claims.add(build_claims(properties, target_item))
    assert not item.write_required(base_filter=base_filter(properties))

    # Write and delete
    new = wbi.item.new()
    new.labels.set(language='en', value=f'WBI integration test instance configuration {RUN_ID}')
    new = new.write(summary='WikibaseIntegrator integration test: instance configuration')
    assert wbi.item.get(new.id).labels.get('en').value == f'WBI integration test instance configuration {RUN_ID}'
    new.delete(reason='WikibaseIntegrator integration test cleanup')
