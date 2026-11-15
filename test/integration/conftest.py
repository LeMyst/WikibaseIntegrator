"""
Configuration for the integration tests.

These tests talk to a REAL Wikibase instance and are deselected by default
(see the pytest addopts in pyproject.toml). Run them with:

    WBI_INTEGRATION_MEDIAWIKI_API_URL=http://localhost:8880/w/api.php \
    WBI_INTEGRATION_USER=admin \
    WBI_INTEGRATION_PASSWORD=change-this-password \
    pytest -m integration

See test/integration/README.md for the docker-compose setup.
"""
import os
from copy import deepcopy

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_helpers import delete_page, mediawiki_api_call_helper

API_URL = os.getenv('WBI_INTEGRATION_MEDIAWIKI_API_URL')
SPARQL_URL = os.getenv('WBI_INTEGRATION_SPARQL_ENDPOINT_URL')
# The first part of the concept URIs of the instance (e.g. http://localhost:8880 for http://localhost:8880/entity/Q1), for the SPARQL queries
WIKIBASE_URL = os.getenv('WBI_INTEGRATION_WIKIBASE_URL')
USER = os.getenv('WBI_INTEGRATION_USER')
PASSWORD = os.getenv('WBI_INTEGRATION_PASSWORD')


@pytest.fixture(scope='session')
def integration_api_url() -> str:
    if not API_URL:
        pytest.skip('WBI_INTEGRATION_MEDIAWIKI_API_URL is not set')
    return API_URL


@pytest.fixture(scope='session', autouse=True)
def integration_config(integration_api_url):
    """
    Point wbi_config to the instance under test, for the whole test session.

    This must be session-scoped (not the more natural function-scoped autouse):
    pytest sets up fixtures broadest-scope-first, so a function-scoped fixture would
    run *after* session/module-scoped ones. `login` (session) and `string_property`
    (module, in test_wikibase_roundtrip.py) both talk to the real instance during their
    own setup, using whatever mediawiki_api_url is in wbi_config at that point. A
    function-scoped fixture would still be pointing at the default Wikidata URL then,
    which mismatches the login object's own URL and raises a ValueError in
    mediawiki_api_call_helper ("mediawiki_api_url can't be different with the one in
    the login object.").

    (The function-scoped, autouse `preserve_config` fixture from the top-level conftest
    still runs per test on top of this and is harmless: since it always executes after
    this session fixture, its snapshot already includes the values set here.)
    """
    original = deepcopy(wbi_config)
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-integration-tests/1.0'
    wbi_config['MEDIAWIKI_API_URL'] = integration_api_url
    if SPARQL_URL:
        wbi_config['SPARQL_ENDPOINT_URL'] = SPARQL_URL
    if WIKIBASE_URL:
        wbi_config['WIKIBASE_URL'] = WIKIBASE_URL
    yield wbi_config
    wbi_config.clear()
    wbi_config.update(original)


@pytest.fixture(scope='session')
def login(integration_api_url, integration_config):
    if not USER or not PASSWORD:
        pytest.skip('WBI_INTEGRATION_USER / WBI_INTEGRATION_PASSWORD are not set')
    return wbi_login.Login(user=USER, password=PASSWORD, mediawiki_api_url=integration_api_url, user_agent='WikibaseIntegrator-integration-tests/1.0')


@pytest.fixture(scope='session')
def delete_entities(login):
    """
    Delete entities by id. The entity returned by write() can't delete itself: the response of wbeditentity has no page
    id or title, and the namespace of the entities depends on the configuration of the instance.
    """

    def delete(entity_ids: list[str]) -> None:
        if not entity_ids:
            return
        entities = mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': '|'.join(entity_ids), 'props': 'info', 'format': 'json'}, allow_anonymous=True)['entities']
        for entity in entities.values():
            delete_page(title=entity['title'], reason='WikibaseIntegrator integration test cleanup', login=login)

    return delete


@pytest.fixture(scope='session')
def query_service(integration_config) -> str:
    """The SPARQL endpoint of the instance, for the fast run mode."""
    if not SPARQL_URL or not WIKIBASE_URL:
        pytest.skip('WBI_INTEGRATION_SPARQL_ENDPOINT_URL / WBI_INTEGRATION_WIKIBASE_URL are not set')
    return SPARQL_URL


@pytest.fixture
def wbi(login):
    return WikibaseIntegrator(login=login)
