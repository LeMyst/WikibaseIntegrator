"""
The configuration of a WikibaseIntegrator instance (#1193): its entities and their fast run use it, the other instances and
wbi_config are left alone.
"""
import copy

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, ExternalID, Item, String
from wikibaseintegrator.models import Form
from wikibaseintegrator.wbi_config import config as wbi_config

from .conftest import MockWikibase, literal, load_fixture
from .test_entity_revision import OLD_REVISION, add_old_revision
from .test_wbi_fastrun import PTYPE_EXTERNAL_ID, SparqlData


@pytest.fixture
def other(requests_mock, wikibase):
    """A second instance, while wbi_config points to the first one (wikibase)."""
    return MockWikibase(requests_mock, base_url='https://other.example.org')


def config_of(instance, **extra):
    return {'MEDIAWIKI_API_URL': instance.mediawiki_api_url, 'SPARQL_ENDPOINT_URL': instance.sparql_endpoint_url, 'WIKIBASE_URL': instance.base_url, **extra}


@pytest.fixture
def wbi_other(other):
    return WikibaseIntegrator(config=config_of(other, USER_AGENT='other-agent/1.0'))


def api_requests(requests_mock, instance):
    return [request for request in requests_mock.request_history if request.url.startswith(instance.mediawiki_api_url)]


class TestConfig:
    def test_default_reads_wbi_config_when_used(self, wikibase):
        wbi = WikibaseIntegrator()
        assert wbi.config['MEDIAWIKI_API_URL'] == wikibase.mediawiki_api_url

        wbi_config['MEDIAWIKI_API_URL'] = 'https://changed.example.org/w/api.php'
        assert wbi.config['MEDIAWIKI_API_URL'] == 'https://changed.example.org/w/api.php'
        assert dict(wbi.config) == wbi_config
        assert len(wbi.config) == len(wbi_config)

    def test_own_values_and_the_others_from_wbi_config(self, other, wbi_other):
        assert wbi_other.config['MEDIAWIKI_API_URL'] == other.mediawiki_api_url
        assert wbi_other.config['TIMEOUT'] == wbi_config['TIMEOUT']
        assert set(wbi_other.config) == set(wbi_config)
        assert len(wbi_other.config) == len(wbi_config)
        assert repr(wbi_other.config).startswith("_InstanceConfig({'MEDIAWIKI_API_URL'")
        # wbi_config is unchanged
        assert wbi_config['MEDIAWIKI_API_URL'] != other.mediawiki_api_url

    def test_the_given_dict_is_copied(self, other):
        values = config_of(other)
        wbi = WikibaseIntegrator(config=values)
        values['WIKIBASE_URL'] = 'https://changed.example.org'
        assert wbi.config['WIKIBASE_URL'] == other.base_url

    def test_read_only(self, wbi_other):
        with pytest.raises(TypeError):
            wbi_other.config['WIKIBASE_URL'] = 'https://changed.example.org'

    def test_unknown_option(self):
        with pytest.raises(ValueError, match='Unknown configuration options: MEDIAWIKI_URL, OTHER. The options are the keys of wbi_config: BACKOFF_MAX_TRIES'):
            WikibaseIntegrator(config={'MEDIAWIKI_URL': 'https://other.example.org/w/api.php', 'OTHER': 1})

    def test_manifest_config(self, other):
        # The values of WikibaseManifest.config() are options of wbi_config
        manifest_config = {'MEDIAWIKI_API_URL': other.mediawiki_api_url, 'MEDIAWIKI_REST_URL': other.mediawiki_rest_url,
                           'MEDIAWIKI_INDEX_URL': other.mediawiki_index_url, 'SPARQL_ENDPOINT_URL': other.sparql_endpoint_url, 'WIKIBASE_URL': other.base_url}
        assert WikibaseIntegrator(config=manifest_config).config['MEDIAWIKI_REST_URL'] == other.mediawiki_rest_url

    def test_entities_and_their_copies_share_the_configuration(self, wbi_other):
        item = wbi_other.item.new()
        assert item.api.config is wbi_other.config
        assert copy.deepcopy(item).api.config is wbi_other.config
        assert copy.copy(item).api.config is wbi_other.config


class TestEntities:
    def test_get_and_write(self, requests_mock, wikibase, other, wbi_other):
        other.add_fixture('item_Q582')

        item = wbi_other.item.get('Q582')
        item.claims.add(String(prop_nr='P1', value='on the other instance'))
        item.write(allow_anonymous=True)

        assert not wikibase.requests
        assert [request['action'] for request in other.requests] == ['wbgetentities', 'wbeditentity']
        assert {request.headers['User-Agent'].split(' ')[0] for request in api_requests(requests_mock, other)} == {'other-agent/1.0'}

    def test_the_default_instance_still_uses_wbi_config(self, wikibase, other, wbi_other):
        wikibase.add_fixture('item_Q582')
        WikibaseIntegrator().item.get('Q582')
        assert [request['action'] for request in wikibase.requests] == ['wbgetentities']
        assert not other.requests

    def test_arguments_take_precedence(self, wikibase, other, wbi_other):
        wikibase.add_fixture('item_Q582')
        wbi_other.item.get('Q582', mediawiki_api_url=wikibase.mediawiki_api_url)
        assert wikibase.requests and not other.requests

    def test_none_arguments_take_the_configuration(self, wikibase, other, wbi_other):
        other.add_fixture('item_Q582')
        wbi_other.item.get('Q582', mediawiki_api_url=None, user_agent=None)
        assert other.requests and not wikibase.requests

    def test_get_a_revision(self, requests_mock, wikibase, other, wbi_other):
        other.add_fixture('item_Q582')
        add_old_revision(other, 'Q582')

        assert wbi_other.item.get('Q582', revision=OLD_REVISION).labels.get('en').value == 'old value'
        assert other.entity_data_requests and not wikibase.entity_data_requests

    def test_get_claims(self, wikibase, other, wbi_other):
        other.add_fixture('item_Q582')
        item = wbi_other.item.new()
        item.id = 'Q582'
        item.get_claims('P31')
        assert [request['action'] for request in other.requests] == ['wbgetclaims']
        assert not wikibase.requests

    def test_delete(self, wikibase, other, wbi_other):
        other.add_fixture('item_Q582')
        item = wbi_other.item.new()
        item.id = 'Q582'
        item.delete(allow_anonymous=True)
        assert [request['action'] for request in other.requests] == ['wbgetentities', 'delete']
        assert other.last_request['pageid'] == '856'
        assert not wikibase.requests

    def test_max_request_size(self, wikibase, other):
        wbi = WikibaseIntegrator(config=config_of(other, MAX_REQUEST_SIZE=2000))
        item = wbi.item.new()
        for number in range(40):
            item.claims.add(String(prop_nr='P1', value=f'value number {number}'))
        item.write(allow_anonymous=True)

        assert len(other.edits) > 2
        assert not wikibase.edits

    def test_lexeme(self, wikibase, other):
        wbi = WikibaseIntegrator(config=config_of(other, DEFAULT_LEXEME_LANGUAGE='Q150'))
        assert wbi.lexeme.new().language == 'Q150'
        assert WikibaseIntegrator().lexeme.new().language == wbi_config['DEFAULT_LEXEME_LANGUAGE']

        other.add_fixture('lexeme_L5')
        lexeme = wbi.lexeme.get('L5')
        form = Form()
        form.representations.set(language='en', value='others')
        lexeme.write_form(form, allow_anonymous=True)
        edited = lexeme.edit_form(form, allow_anonymous=True)
        lexeme.remove_form(edited, allow_anonymous=True)

        assert [request['action'] for request in other.requests] == ['wbgetentities', 'wbladdform', 'wbleditformelements', 'wblremoveform']
        assert not wikibase.requests

    def test_mediainfo_get_by_title(self, wikibase, other, wbi_other):
        other.add_fixture('mediainfo_M75908279')
        assert wbi_other.mediainfo.get_by_title(titles='File:2018-07-05-budapest-buda-hill.jpg').id == 'M75908279'
        assert other.requests and not wikibase.requests

    def test_get_entity_url(self, other, wbi_other):
        item = wbi_other.item.new()
        item.id = 'Q42'
        assert item.get_entity_url() == f'{other.base_url}/entity/Q42'
        assert item.get_entity_url(wikibase_url='https://given.example.org') == 'https://given.example.org/entity/Q42'


class TestFastRun:
    def test_write_required_queries_the_endpoint_of_the_instance(self, requests_mock, wikibase, other, wbi_other):
        other.add_property('P356', 'external-id')
        sparql_data = SparqlData(other)
        sparql_data.statement('Q99', 'P356', literal('10.1001/ARCHDERM.1979.04010090001003'), PTYPE_EXTERNAL_ID)

        item = wbi_other.item.new()
        item.id = 'Q99'
        item.claims.add(ExternalID(value='10.1001/ARCHDERM.1979.04010090001003', prop_nr='P356'))

        assert item.write_required(base_filter=[BaseDataType(prop_nr='P356')]) is False
        assert other.sparql_queries and not wikibase.sparql_queries
        assert any(f'<{other.base_url}/prop/' in query for query in other.sparql_queries)
        assert not any(wikibase.base_url in query for query in other.sparql_queries)
        sparql_requests = [request for request in requests_mock.request_history if request.url == other.sparql_endpoint_url]
        assert {request.headers['User-Agent'].split(' ')[0] for request in sparql_requests} == {'other-agent/1.0'}

        assert len(wbi_fastrun.fastrun_store) == 1
        container = wbi_fastrun.fastrun_store[0]
        assert (container.sparql_endpoint_url, container.wikibase_url, container.mediawiki_api_url) == (other.sparql_endpoint_url, other.base_url, other.mediawiki_api_url)

    def test_the_property_types_come_from_the_instance(self, wikibase, other, wbi_other):
        # A graph without the properties: their types are read from the MediaWiki API of the instance
        other.add_property('P356', 'external-id')
        SparqlData(other).statement('Q99', 'P356', literal('10.1001/ARCHDERM.1979.04010090001003'), None)

        item = wbi_other.item.new()
        item.id = 'Q99'
        item.claims.add(ExternalID(value='10.1001/ARCHDERM.1979.04010090001003', prop_nr='P356'))

        assert item.write_required(base_filter=[BaseDataType(prop_nr='P356')]) is False
        assert [request['action'] for request in other.requests] == ['wbgetentities']
        assert not wikibase.requests

    def test_the_entity_values_use_the_wikibase_url_of_the_container(self, wikibase, other, wbi_other):
        other.add_property('P31', 'wikibase-item')
        SparqlData(other).statement('Q99', 'P31', {'type': 'uri', 'value': f'{other.base_url}/entity/Q5'}, 'http://wikiba.se/ontology#WikibaseItem')

        item = wbi_other.item.new()
        item.id = 'Q99'
        item.claims.add(Item(value='Q5', prop_nr='P31'))

        assert item.write_required(base_filter=[BaseDataType(prop_nr='P31')]) is False

    def test_one_container_per_instance(self, wikibase, other, wbi_other):
        base_filter = [BaseDataType(prop_nr='P356')]
        default = wbi_fastrun.get_fastrun_container(base_filter=base_filter)
        on_other = wbi_fastrun.get_fastrun_container(base_filter=base_filter, sparql_endpoint_url=other.sparql_endpoint_url, wikibase_url=other.base_url,
                                                     mediawiki_api_url=other.mediawiki_api_url)

        assert default is not on_other
        assert wbi_fastrun.get_fastrun_container(base_filter=base_filter) is default
        assert wbi_fastrun.get_fastrun_container(base_filter=base_filter, sparql_endpoint_url=other.sparql_endpoint_url, wikibase_url=other.base_url,
                                                 mediawiki_api_url=other.mediawiki_api_url, user_agent='agent/2') is on_other
        assert on_other.user_agent == 'agent/2'
        # Same endpoint and Wikibase URL, another MediaWiki API: the types of the properties may differ
        assert wbi_fastrun.get_fastrun_container(base_filter=base_filter, mediawiki_api_url=other.mediawiki_api_url) not in (default, on_other)

    def test_clear_fastrun_store(self, wikibase):
        container = wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P356')])
        wbi_fastrun.clear_fastrun_store()

        assert not wbi_fastrun.fastrun_store
        assert wbi_fastrun.get_fastrun_container(base_filter=[BaseDataType(prop_nr='P356')]) is not container


def test_the_fixture_instances_are_independent(other, wikibase):
    # Sanity check of the test setup: both mocks answer on their own URL
    other.add_entity(load_fixture('item_Q582'))
    assert 'Q582' not in wikibase.entities
