"""
Tests for the wbi_backoff decorator: retry on transient HTTP/JSON failures,
give up on permanent ones.
"""
import pytest
import requests
import ujson

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config


@pytest.fixture(autouse=True)
def fast_backoff():
    config['BACKOFF_MAX_TRIES'] = 2
    config['BACKOFF_MAX_VALUE'] = 1
    # preserve_config (autouse, from conftest) restores the original values


def test_http_error_is_retried_then_raised(requests_mock):
    requests_mock.get('https://unstable.example.org/api', status_code=400, text='Bad Request')

    @wbi_backoff()
    def bad_http_code():
        result = requests.get('https://unstable.example.org/api')
        result.raise_for_status()

    with pytest.raises(requests.RequestException):
        bad_http_code()

    # BACKOFF_MAX_TRIES = 2: the call is retried exactly once.
    assert requests_mock.call_count == 2


def test_success_is_not_retried(requests_mock):
    requests_mock.get('https://stable.example.org/api', text='{"status": "ok"}')

    @wbi_backoff()
    def good_http_code():
        result = requests.get('https://stable.example.org/api')
        result.raise_for_status()
        return result.status_code

    assert good_http_code() == 200
    assert requests_mock.call_count == 1


def test_connection_error_is_retried(requests_mock):
    requests_mock.get('https://unreachable.example.org/api', exc=requests.exceptions.ConnectionError)

    @wbi_backoff()
    def bad_request():
        requests.get('https://unreachable.example.org/api')

    with pytest.raises(requests.RequestException):
        bad_request()

    assert requests_mock.call_count == 2


def test_empty_json_payload_is_retried():
    import json

    attempts = []

    @wbi_backoff()
    def bad_json():
        attempts.append(1)
        json.loads('')

    with pytest.raises(ValueError):
        bad_json()

    # "Expecting value: line 1 column 1 (char 0)" is considered transient and retried.
    assert len(attempts) == 2


def test_malformed_json_gives_up_immediately():
    attempts = []

    @wbi_backoff()
    def malformed_json():
        attempts.append(1)
        ujson.loads('<xml>I failed :(</xml>')

    with pytest.raises(ValueError):
        malformed_json()

    # A real parse error (not an empty payload) must not be retried.
    assert len(attempts) == 1
