"""
Tests for the WikibaseManifest support. The manifest is the one of https://wikibase.world (2026-10-31), served by
requests-mock.
"""
from copy import deepcopy

import pytest
import requests

from wikibaseintegrator import wbi_manifest
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import MissingExtensionError

REST_URL = 'https://wikibase.world/w/rest.php'
MANIFEST_URL = REST_URL + '/wikibase-manifest/v0/manifest'

MANIFEST = {
    'name': 'Wikibase World',
    'root_script_url': 'https://wikibase.world/w',
    'main_page_url': 'https://wikibase.world/wiki/Project:Home',
    'max_lag': 5,
    'api': {'action': 'https://wikibase.world/w/api.php', 'rest': 'https://wikibase.world/w/rest.php'},
    'equiv_entities': {'wikidata.org': {'properties': {'P31': 'P3', 'P1630': 'P16', 'P279': 'P27', 'P2888': 'P4'}, 'items': {'Q5': 'Q8'}}},
    'local_rdf_namespaces': {
        '': 'https://wikibase.world/entity/',
        'data': 'https://wikibase.world/wiki/Special:EntityData/',
        'p': 'https://wikibase.world/prop/',
        't': 'https://wikibase.world/prop/direct/',
    },
    'external_services': {
        'queryservice_ui': 'https://wikibase.world/query',
        'queryservice': 'https://wikibase.world/query/sparql',
        'quickstatements': 'https://wikibase.world/tools/quickstatements',
    },
    'local_entities': {'item': {'namespace_id': 120, 'namespace_name': 'Item'}, 'property': {'namespace_id': 122, 'namespace_name': 'Property'}},
    'oauth': {'registration_page': 'https://wikibase.world/wiki/Special:OAuthConsumerRegistration'},
}

# The only required parts: an instance without query service, OAuth nor equivalences
MINIMAL_MANIFEST = {
    'name': 'Minimal',
    'root_script_url': 'https://minimal.example.org/w/',
    'main_page_url': 'https://minimal.example.org/wiki/Main_Page',
    'api': {'action': 'https://minimal.example.org/w/api.php', 'rest': 'https://minimal.example.org/w/rest.php'},
    'local_rdf_namespaces': {'': 'https://minimal.example.org/concept/'},
}


@pytest.fixture
def manifest_mock(requests_mock):
    return requests_mock.get(MANIFEST_URL, json=MANIFEST)


class TestGetManifest:
    def test_from_the_rest_api(self, manifest_mock):
        manifest = wbi_manifest.get_manifest(REST_URL)

        assert manifest.name == 'Wikibase World'
        assert manifest.mediawiki_api_url == 'https://wikibase.world/w/api.php'
        assert manifest.mediawiki_rest_url == REST_URL
        assert manifest.mediawiki_index_url == 'https://wikibase.world/w/index.php'
        assert manifest.sparql_endpoint_url == 'https://wikibase.world/query/sparql'
        assert manifest.wikibase_url == 'https://wikibase.world'
        assert manifest.max_lag == 5
        assert manifest.external_services['quickstatements'] == 'https://wikibase.world/tools/quickstatements'
        assert list(manifest.local_entities) == ['item', 'property']
        assert manifest.oauth_registration_page == 'https://wikibase.world/wiki/Special:OAuthConsumerRegistration'
        assert manifest.raw == MANIFEST
        assert manifest_mock.last_request.headers['User-Agent'].startswith('WikibaseIntegrator-pytest/1.0')

    @pytest.mark.parametrize('url', [MANIFEST_URL, REST_URL + '/', MANIFEST_URL + '/'])
    def test_url_forms(self, manifest_mock, url):
        assert wbi_manifest.get_manifest(url).name == 'Wikibase World'
        assert manifest_mock.last_request.url == MANIFEST_URL

    def test_rest_api_of_the_configuration(self, manifest_mock):
        wbi_config['MEDIAWIKI_REST_URL'] = REST_URL

        assert wbi_manifest.get_manifest().name == 'Wikibase World'

    def test_instance_without_the_extension(self, requests_mock):
        # The answer of Wikidata, which doesn't have the extension
        requests_mock.get('https://www.wikidata.org/w/rest.php/wikibase-manifest/v0/manifest', status_code=404, json={
            'errorKey': 'rest-no-match', 'httpCode': 404, 'httpReason': 'Not Found',
            'messageTranslations': {'en': 'The requested relative path (/wikibase-manifest/v0/manifest) did not match any known handler'}})

        with pytest.raises(MissingExtensionError, match='WikibaseManifest') as error:
            wbi_manifest.get_manifest('https://www.wikidata.org/w/rest.php')

        assert error.value.extension == 'WikibaseManifest'
        assert error.value.code == 'rest-no-match'

    def test_not_found_without_json(self, requests_mock):
        requests_mock.get(MANIFEST_URL, status_code=404, text='<html>Not Found</html>')

        with pytest.raises(MissingExtensionError):
            wbi_manifest.get_manifest(REST_URL)

    def test_other_errors(self, requests_mock):
        requests_mock.get(MANIFEST_URL, status_code=500, text='Internal error')

        with pytest.raises(requests.HTTPError):
            wbi_manifest.get_manifest(REST_URL)


class TestManifest:
    def test_local_id(self):
        manifest = wbi_manifest.WikibaseManifest.from_json(MANIFEST)

        assert manifest.local_id('P31') == 'P3'
        assert manifest.local_id('Q5') == 'Q8'
        assert manifest.local_id('P17') is None
        assert manifest.local_id('P31', hub='other.example.org') is None

    def test_config(self):
        assert wbi_manifest.WikibaseManifest.from_json(MANIFEST).config() == {
            'MEDIAWIKI_API_URL': 'https://wikibase.world/w/api.php',
            'MEDIAWIKI_REST_URL': 'https://wikibase.world/w/rest.php',
            'MEDIAWIKI_INDEX_URL': 'https://wikibase.world/w/index.php',
            'WIKIBASE_URL': 'https://wikibase.world',
            'SPARQL_ENDPOINT_URL': 'https://wikibase.world/query/sparql',
        }

    def test_apply_to_the_configuration(self):
        user_agent = wbi_config['USER_AGENT']

        wbi_manifest.WikibaseManifest.from_json(MANIFEST).apply()

        assert wbi_config['MEDIAWIKI_API_URL'] == 'https://wikibase.world/w/api.php'
        assert wbi_config['SPARQL_ENDPOINT_URL'] == 'https://wikibase.world/query/sparql'
        assert wbi_config['WIKIBASE_URL'] == 'https://wikibase.world'
        # The other options are kept
        assert wbi_config['USER_AGENT'] == user_agent

    def test_apply_to_another_configuration(self):
        target: dict = {'TIMEOUT': 30}

        wbi_manifest.WikibaseManifest.from_json(MANIFEST).apply(target)

        assert target['MEDIAWIKI_API_URL'] == 'https://wikibase.world/w/api.php'
        assert target['TIMEOUT'] == 30

    def test_minimal_manifest(self):
        before = deepcopy(dict(wbi_config))
        manifest = wbi_manifest.WikibaseManifest.from_json(MINIMAL_MANIFEST)

        assert manifest.sparql_endpoint_url is None
        assert manifest.max_lag is None
        assert manifest.oauth_registration_page is None
        assert manifest.local_id('P31') is None
        assert manifest.mediawiki_index_url == 'https://minimal.example.org/w/index.php'
        # The concept URI doesn't end with /entity/: no Wikibase URL to derive
        assert manifest.wikibase_url is None
        # Without a query service nor a Wikibase URL, apply() leaves them as they are
        manifest.apply()
        assert wbi_config['SPARQL_ENDPOINT_URL'] == before['SPARQL_ENDPOINT_URL']
        assert wbi_config['WIKIBASE_URL'] == before['WIKIBASE_URL']
        assert wbi_config['MEDIAWIKI_API_URL'] == 'https://minimal.example.org/w/api.php'
