import os
from typing import Final

from wikibaseintegrator.wbi_config import config as wbi_config

# Centralized IDs so tests can run against either Wikidata defaults or a seeded local Wikibase.
ITEM_EARTH_ID: Final[str] = os.getenv('WBI_TEST_ITEM_EARTH_ID', 'Q2')
ITEM_CITY_ID: Final[str] = os.getenv('WBI_TEST_ITEM_CITY_ID', 'Q582')
ITEM_GENE_ID: Final[str] = os.getenv('WBI_TEST_ITEM_GENE_ID', 'Q10874')
ITEM_SITELINK_ID: Final[str] = os.getenv('WBI_TEST_ITEM_SITELINK_ID', 'Q622901')
ITEM_NO_SITELINK_ID: Final[str] = os.getenv('WBI_TEST_ITEM_NO_SITELINK_ID', 'Q27869338')
PROPERTY_AUTHOR_ID: Final[str] = os.getenv('WBI_TEST_PROPERTY_AUTHOR_ID', 'P50')
LEXEME_MAIN_ID: Final[str] = os.getenv('WBI_TEST_LEXEME_MAIN_ID', 'L5')
MEDIAINFO_MAIN_ID: Final[str] = os.getenv('WBI_TEST_MEDIAINFO_MAIN_ID', 'M75908279')


def configure_endpoints_from_env() -> None:
    """Override default endpoints for tests when local Wikibase env vars are set."""
    endpoint_mapping = {
        'WBI_MEDIAWIKI_API_URL': 'MEDIAWIKI_API_URL',
        'WBI_MEDIAWIKI_INDEX_URL': 'MEDIAWIKI_INDEX_URL',
        'WBI_MEDIAWIKI_REST_URL': 'MEDIAWIKI_REST_URL',
        'WBI_SPARQL_ENDPOINT_URL': 'SPARQL_ENDPOINT_URL',
        'WBI_WIKIBASE_URL': 'WIKIBASE_URL'
    }

    for env_name, config_key in endpoint_mapping.items():
        env_value = os.getenv(env_name)
        if env_value:
            wbi_config[config_key] = env_value
