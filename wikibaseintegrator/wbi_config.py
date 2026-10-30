"""
Config global options
Options can be changed at run time. See test/test_wbi_backoff.py for usage example

Options:
BACKOFF_MAX_TRIES: maximum number of tries of a SPARQL query or a login failing with a transient error (see wbi_backoff).
                   Default: 5
                   Set to None to retry indefinitely, or to 1 to disable the retries
BACKOFF_MAX_VALUE: maximum number of seconds to wait before retrying. The wait doubles after each try (1, 2, 4... seconds)
                   up to this number. Also caps the delay asked by the SPARQL endpoint with an HTTP 429 response.
                   Default: 3600 (one hour)
USER_AGENT:        Complementary user agent string used for http requests. Both to Wikibase api, query service and others.
                   See: https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
TIMEOUT:           Timeout (in seconds) passed to every HTTP request, either a single value or a (connect, read) tuple.
                   Prevents a silent/unresponsive server from blocking the process indefinitely.
                   Set to None to disable (wait forever). Default: (5, 300)
SPARQL_AUTH:       Default authentication used by wbi_helpers.execute_sparql_query() (and so by the fast run mode) when the
                   SPARQL endpoint is protected. Either a (username, password) tuple for HTTP Basic auth or any
                   requests.auth.AuthBase instance. Default: None (no authentication)
MAX_REQUEST_SIZE:  Maximum size (in bytes) of the entity data sent by a write, once form-encoded. A larger write is
                   split into several edits: the first one with everything but the statements and as many statements as
                   fit, then the remaining statements. Use it with a Wikibase instance rejecting large requests with an
                   HTTP 413 error (e.g. Wikibase.cloud), with a margin for the other parameters of the request.
                   Default: None (never split)
"""

from typing import Any

config: dict[str, Any] = {
    'BACKOFF_MAX_TRIES': 5,
    'BACKOFF_MAX_VALUE': 3600,
    'USER_AGENT': None,
    'TIMEOUT': (5, 300),
    'PROPERTY_CONSTRAINT_PID': 'P2302',
    'DISTINCT_VALUES_CONSTRAINT_QID': 'Q21502410',
    'COORDINATE_GLOBE_QID': 'http://www.wikidata.org/entity/Q2',
    'CALENDAR_MODEL_QID': 'http://www.wikidata.org/entity/Q1985727',
    'MEDIAWIKI_API_URL': 'https://www.wikidata.org/w/api.php',
    'MEDIAWIKI_INDEX_URL': 'https://www.wikidata.org/w/index.php',
    'MEDIAWIKI_REST_URL': 'https://www.wikidata.org/w/rest.php',
    'SPARQL_ENDPOINT_URL': 'https://query.wikidata.org/sparql',
    'SPARQL_AUTH': None,
    'MAX_REQUEST_SIZE': None,
    'WIKIBASE_URL': 'http://www.wikidata.org',
    'DEFAULT_LANGUAGE': 'en',
    'DEFAULT_LEXEME_LANGUAGE': 'Q1860',
    'SPARQL_QUERY_LIMIT': 10000
}
