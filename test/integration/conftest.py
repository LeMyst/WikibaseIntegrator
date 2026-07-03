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

import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.wbi_config import config as wbi_config

API_URL = os.getenv('WBI_INTEGRATION_MEDIAWIKI_API_URL')
SPARQL_URL = os.getenv('WBI_INTEGRATION_SPARQL_ENDPOINT_URL')
USER = os.getenv('WBI_INTEGRATION_USER')
PASSWORD = os.getenv('WBI_INTEGRATION_PASSWORD')


@pytest.fixture(scope='session')
def integration_api_url() -> str:
    if not API_URL:
        pytest.skip('WBI_INTEGRATION_MEDIAWIKI_API_URL is not set')
    return API_URL


@pytest.fixture(autouse=True)
def integration_config(integration_api_url, preserve_config):
    """Point wbi_config to the instance under test."""
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-integration-tests/1.0'
    wbi_config['MEDIAWIKI_API_URL'] = integration_api_url
    if SPARQL_URL:
        wbi_config['SPARQL_ENDPOINT_URL'] = SPARQL_URL


@pytest.fixture(scope='session')
def login(integration_api_url):
    if not USER or not PASSWORD:
        pytest.skip('WBI_INTEGRATION_USER / WBI_INTEGRATION_PASSWORD are not set')
    return wbi_login.Login(user=USER, password=PASSWORD, mediawiki_api_url=integration_api_url, user_agent='WikibaseIntegrator-integration-tests/1.0')


@pytest.fixture
def wbi(login):
    return WikibaseIntegrator(login=login)
