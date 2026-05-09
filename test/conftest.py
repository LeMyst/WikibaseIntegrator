import os
from test.wikibase_test_config import configure_endpoints_from_env

import pytest


def pytest_configure(config):
    config.addinivalue_line('markers', 'external_network: test reaches external network resources')
    config.addinivalue_line('markers', 'wikibase_integration: test requires a reachable Wikibase API endpoint')
    config.addinivalue_line('markers', 'requires_sparql: test requires a SPARQL endpoint')
    config.addinivalue_line('markers', 'requires_commons: test requires Wikimedia Commons MediaInfo data')


def pytest_collection_modifyitems(config, items):
    run_external = os.getenv('WBI_RUN_EXTERNAL_NETWORK_TESTS') == '1'

    if run_external:
        return

    skip_external = pytest.mark.skip(reason='external network tests disabled (set WBI_RUN_EXTERNAL_NETWORK_TESTS=1 to enable)')
    for item in items:
        if any(marker.name in {'external_network', 'wikibase_integration', 'requires_sparql', 'requires_commons'} for marker in item.iter_markers()):
            item.add_marker(skip_external)


@pytest.fixture(scope='session', autouse=True)
def _configure_test_endpoints():
    configure_endpoints_from_env()
