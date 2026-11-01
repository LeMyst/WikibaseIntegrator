import pytest

from wikibaseintegrator.wbi_exceptions import MaxRetriesReachedException
from wikibaseintegrator.wbi_helpers import mediawiki_api_call

URL = 'https://throttled.example.org/w/api.php'


@pytest.fixture
def slept(monkeypatch):
    """The waits between the tries."""
    waits: list[float] = []
    monkeypatch.setattr('wikibaseintegrator.wbi_helpers.sleep', waits.append)
    return waits


class TestRateLimited:
    def test_core_rate_limit_is_retried(self, requests_mock, slept):
        # The rate limit of MediaWiki core (ApiBase): the 'ratelimited' code, without messages in the default error format
        throttled = {'error': {'code': 'ratelimited', 'info': "As an anti-abuse measure, you are limited from performing this action too many times in a short space of time."}}
        requests_mock.post(URL, [{'json': throttled}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=URL, max_retries=3, retry_after=7) == {'success': 1}
        assert slept == [7]
        assert requests_mock.call_count == 2

    def test_wikibase_rate_limit_is_still_retried(self, requests_mock, slept):
        # The rate limit inside a Wikibase failed-save error, with its messages
        throttled = {'error': {'code': 'failed-save', 'info': 'The save has failed.', 'messages': [{'name': 'wikibase-api-failed-save'}, {'name': 'actionthrottledtext'}]}}
        requests_mock.post(URL, [{'json': throttled}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=URL, max_retries=3, retry_after=7) == {'success': 1}
        assert slept == [7]

    def test_message_without_name(self, requests_mock, slept):
        # A message without a name used to raise KeyError
        throttled = {'error': {'code': 'ratelimited', 'info': 'Rate limited', 'messages': [{'html': {'*': 'Rate limited'}}]}}
        requests_mock.post(URL, [{'json': throttled}, {'json': {'success': 1}}])

        assert mediawiki_api_call('POST', mediawiki_api_url=URL, max_retries=3, retry_after=7) == {'success': 1}

    def test_rate_limit_until_the_retries_run_out(self, requests_mock, slept):
        requests_mock.post(URL, json={'error': {'code': 'ratelimited', 'info': 'Rate limited'}})

        with pytest.raises(MaxRetriesReachedException):
            mediawiki_api_call('POST', mediawiki_api_url=URL, max_retries=3, retry_after=7)
        assert requests_mock.call_count == 3
