"""
The time limit of a SPARQL query (query_timeout, config['SPARQL_QUERY_TIMEOUT']) and the queries stopped by the endpoint
at its time limit (SPARQLTimeoutError, not retried).
"""
from urllib.parse import parse_qs

import pytest
import requests

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import ExternalID
from wikibaseintegrator.wbi_backoff import SPARQLTimeoutError
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import WikibaseIntegratorError
from wikibaseintegrator.wbi_helpers import execute_sparql_query

URL = 'https://query.example.org/sparql'
QUERY = 'SELECT * WHERE { ?a ?b ?c . }'
EMPTY_RESULTS: dict = {'head': {'vars': []}, 'results': {'bindings': []}}

# The beginning of the answer of the Wikidata Query Service to a query stopped at its time limit (HTTP 500)
BLAZEGRAPH_TIMEOUT = '''SPARQL-QUERY: queryStr=SELECT (COUNT(*) AS ?c) WHERE { ?s wdt:P31 wd:Q5 . ?s wdt:P21 ?g }
java.util.concurrent.TimeoutException
\tat java.util.concurrent.FutureTask.get(FutureTask.java:205)
\tat com.bigdata.rdf.sail.webapp.BigdataServlet.submitApiTask(BigdataServlet.java:292)
'''


def form(request) -> dict[str, str]:
    """The form-encoded body of a SPARQL request."""
    return {key: values[0] for key, values in parse_qs(request.text).items()}


class TestQueryTimeout:
    def test_no_timeout_by_default(self, requests_mock):
        requests_mock.post(URL, json=EMPTY_RESULTS)

        execute_sparql_query(QUERY, endpoint=URL)

        assert 'maxQueryTimeMillis' not in form(requests_mock.last_request)

    @pytest.mark.parametrize(('query_timeout', 'expected'), [(5, '5000'), (2.5, '2500'), (0.0001, '1')])
    def test_query_timeout(self, requests_mock, query_timeout, expected):
        requests_mock.post(URL, json=EMPTY_RESULTS)

        execute_sparql_query(QUERY, endpoint=URL, query_timeout=query_timeout)

        assert form(requests_mock.last_request)['maxQueryTimeMillis'] == expected

    def test_config_default(self, requests_mock):
        requests_mock.post(URL, json=EMPTY_RESULTS)
        wbi_config['SPARQL_QUERY_TIMEOUT'] = 10

        execute_sparql_query(QUERY, endpoint=URL)
        assert form(requests_mock.last_request)['maxQueryTimeMillis'] == '10000'

        # The parameter overrides the configuration
        execute_sparql_query(QUERY, endpoint=URL, query_timeout=3)
        assert form(requests_mock.last_request)['maxQueryTimeMillis'] == '3000'

    @pytest.mark.parametrize('query_timeout', [0, -1])
    def test_invalid_query_timeout(self, requests_mock, query_timeout):
        requests_mock.post(URL, json=EMPTY_RESULTS)

        with pytest.raises(ValueError, match='query_timeout must be a positive number of seconds'):
            execute_sparql_query(QUERY, endpoint=URL, query_timeout=query_timeout)

        assert requests_mock.call_count == 0

    def test_fastrun_queries(self, wikibase, requests_mock):
        wbi_config['SPARQL_QUERY_TIMEOUT'] = 30
        container = wbi_fastrun.FastRunContainer(base_filter=[ExternalID(prop_nr='P2')], cache=False)

        container.get_entities(claims=[ExternalID(value='abc', prop_nr='P2')])

        sparql_requests = [request for request in requests_mock.request_history if request.url == wikibase.sparql_endpoint_url]
        assert sparql_requests
        assert all(form(request)['maxQueryTimeMillis'] == '30000' for request in sparql_requests)


class TestStoppedQuery:
    def test_stopped_query_is_not_retried(self, requests_mock):
        requests_mock.post(URL, status_code=500, text=BLAZEGRAPH_TIMEOUT)

        with pytest.raises(SPARQLTimeoutError, match='stopped at the time limit of the SPARQL endpoint') as excinfo:
            execute_sparql_query(QUERY, endpoint=URL, query_timeout=2)

        assert requests_mock.call_count == 1
        # Still caught by the code catching the HTTP errors, or the errors of WikibaseIntegrator
        assert isinstance(excinfo.value, requests.HTTPError)
        assert isinstance(excinfo.value, WikibaseIntegratorError)
        assert excinfo.value.response.status_code == 500

    def test_stopped_query_without_query_timeout(self, requests_mock):
        # The limit of the endpoint itself (60 seconds on the Wikidata Query Service)
        requests_mock.post(URL, status_code=500, text=BLAZEGRAPH_TIMEOUT.replace('java.util.concurrent.TimeoutException', 'com.bigdata.bop.engine.QueryTimeoutException'))

        with pytest.raises(SPARQLTimeoutError):
            execute_sparql_query(QUERY, endpoint=URL)

        assert requests_mock.call_count == 1

    def test_other_server_errors_are_retried(self, requests_mock):
        requests_mock.post(URL, [{'status_code': 500, 'text': 'java.lang.NullPointerException'}, {'json': EMPTY_RESULTS}])

        assert execute_sparql_query(QUERY, endpoint=URL)['results']['bindings'] == []
        assert requests_mock.call_count == 2
