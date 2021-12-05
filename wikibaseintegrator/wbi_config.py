"""
Config global options
Options can be changed at run time. See tests/test_backoff.py for usage example

Options:
BACKOFF_MAX_TRIES: maximum number of times to retry failed request to wikidata endpoint.
                   Default: None (retry indefinitely)
                   To disable retry, set value to 1
BACKOFF_MAX_VALUE: maximum number of seconds to wait before retrying. wait time will increase to this number
                   Default: 3600 (one hour)
USER_AGENT:        Complementary user agent string used for http requests. Both to Wikibase api, query service and others.
                   See: https://meta.wikimedia.org/wiki/User-Agent_policy
"""

from typing import Dict, Union

config: Dict[str, Union[str, int, None, bool]] = {
    'BACKOFF_MAX_TRIES': 5,
    'BACKOFF_MAX_VALUE': 3600,
    'USER_AGENT': None,
    'PROPERTY_CONSTRAINT_PID': 'P2302',
    'DISTINCT_VALUES_CONSTRAINT_QID': 'Q21502410',
    'COORDINATE_GLOBE_QID': 'http://www.wikidata.org/entity/Q2',
    'CALENDAR_MODEL_QID': 'http://www.wikidata.org/entity/Q1985727',
    'MEDIAWIKI_API_URL': 'https://www.wikidata.org/w/api.php',
    'MEDIAWIKI_INDEX_URL': 'https://www.wikidata.org/w/index.php',
    'MEDIAWIKI_REST_URL': 'https://www.wikidata.org/w/rest.php',
    'SPARQL_ENDPOINT_URL': 'https://query.wikidata.org/sparql',
    'WIKIBASE_URL': 'http://www.wikidata.org',
    'DEFAULT_LANGUAGE': 'en',
    'DEFAULT_LEXEME_LANGUAGE': 'Q1860'
}
