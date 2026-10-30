"""
Tests for the wbi_backoff decorator: retry on transient HTTP/JSON failures,
give up on permanent ones.
"""
import time

import pytest
import requests
import ujson

from wikibaseintegrator.wbi_backoff import RetryAfterError, wbi_backoff, wbi_backoff_backoff_hdlr, wbi_backoff_wait
from wikibaseintegrator.wbi_config import config


@pytest.fixture(autouse=True)
def fast_backoff():
    config['BACKOFF_MAX_TRIES'] = 2
    config['BACKOFF_MAX_VALUE'] = 1
    # preserve_config (autouse, from conftest) restores the original values


@pytest.mark.parametrize('status_code', [408, 429, 500, 502, 503, 504])
def test_transient_http_error_is_retried_then_raised(requests_mock, status_code):
    requests_mock.get('https://unstable.example.org/api', status_code=status_code, text='Error')

    @wbi_backoff()
    def bad_http_code():
        result = requests.get('https://unstable.example.org/api')
        result.raise_for_status()

    with pytest.raises(requests.HTTPError):
        bad_http_code()

    # BACKOFF_MAX_TRIES = 2: the call is retried exactly once.
    assert requests_mock.call_count == 2


@pytest.mark.parametrize('status_code', [400, 401, 403, 404])
def test_client_error_gives_up_immediately(requests_mock, status_code):
    # A malformed request or missing credentials get the same answer on every try
    requests_mock.get('https://unstable.example.org/api', status_code=status_code, text='Error')

    @wbi_backoff()
    def bad_http_code():
        result = requests.get('https://unstable.example.org/api')
        result.raise_for_status()

    with pytest.raises(requests.HTTPError):
        bad_http_code()

    assert requests_mock.call_count == 1


def test_wait_is_exponential_and_capped():
    config['BACKOFF_MAX_VALUE'] = 5

    assert [wbi_backoff_wait(tries, requests.ConnectionError()) for tries in range(1, 6)] == [1, 2, 4, 5, 5]


def test_wait_uses_the_retry_after_delay():
    config['BACKOFF_MAX_VALUE'] = 60

    # The delay asked by the server replaces the exponential delay, capped by BACKOFF_MAX_VALUE
    assert wbi_backoff_wait(1, RetryAfterError(retry_after=30)) == 30
    assert wbi_backoff_wait(1, RetryAfterError(retry_after=120)) == 60


def test_waits_between_the_tries(monkeypatch):
    config['BACKOFF_MAX_TRIES'] = 4
    config['BACKOFF_MAX_VALUE'] = 3600
    slept: list[float] = []
    monkeypatch.setattr(time, 'sleep', slept.append)
    attempts = []

    @wbi_backoff()
    def unreachable():
        attempts.append(1)
        raise requests.exceptions.ConnectionError

    with pytest.raises(requests.exceptions.ConnectionError):
        unreachable()

    # No wait after the last try
    assert len(attempts) == 4 and slept == [1, 2, 4]


def test_unlimited_tries():
    config['BACKOFF_MAX_TRIES'] = None
    attempts = []

    @wbi_backoff()
    def flaky():
        attempts.append(1)
        if len(attempts) < 8:
            raise requests.exceptions.Timeout
        return 'ok'

    assert flaky() == 'ok' and len(attempts) == 8


def test_other_exceptions_are_not_retried():
    attempts = []

    @wbi_backoff()
    def broken():
        attempts.append(1)
        raise KeyError('not a network error')

    with pytest.raises(KeyError):
        broken()

    assert len(attempts) == 1


def test_decorated_function_keeps_its_metadata():
    @wbi_backoff()
    def documented(value: int) -> int:
        """Docstring kept"""
        return value

    assert documented.__name__ == 'documented' and documented.__doc__ == 'Docstring kept'
    assert documented(3) == 3


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


def test_credentials_are_not_logged(caplog):
    details = {'wait': 1.0, 'tries': 1, 'args': ('SELECT',), 'kwargs': {'auth': ('user', 'secret'), 'headers': {'Authorization': 'Bearer token'}, 'max_retries': 3}}

    wbi_backoff_backoff_hdlr(details)

    assert 'secret' not in caplog.text
    assert 'Bearer token' not in caplog.text
    # Non-sensitive kwargs are still logged
    assert "'max_retries': 3" in caplog.text
