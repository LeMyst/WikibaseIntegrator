import time

import pytest

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

TOKEN = {'access_token': 'oauth2-access-token', 'token_type': 'Bearer', 'expires_in': 14400}


@pytest.fixture(autouse=True)
def q582(wikibase):
    wikibase.add_fixture('item_Q582')


@pytest.fixture
def token_endpoint(wikibase, requests_mock):
    return requests_mock.post(wikibase.mediawiki_rest_url + '/oauth2/access_token', json=TOKEN)


def expire(login, seconds_left):
    """Make the access token of the session expire in seconds_left seconds (in the past when negative)."""
    login.session.token = {**login.session.token, 'expires_in': seconds_left, 'expires_at': time.time() + seconds_left}


def read(login):
    return mediawiki_api_call_helper(data={'action': 'wbgetentities', 'ids': 'Q582', 'format': 'json'}, login=login, allow_anonymous=True)


class TestOAuth2AccessTokenExpiry:
    def test_expired_access_token_is_fetched_again_before_a_read(self, wikibase, token_endpoint):
        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        fetches = token_endpoint.call_count
        expire(login, -10)

        # A read doesn't renew the edit credentials: it used to raise oauthlib's TokenExpiredError before sending the request
        assert 'Q582' in read(login)['entities']
        assert token_endpoint.call_count == fetches + 1
        assert login.session.token['expires_at'] > time.time() + 3600

    def test_access_token_about_to_expire_is_fetched_again(self, wikibase, token_endpoint):
        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        fetches = token_endpoint.call_count
        expire(login, 30)

        read(login)
        assert token_endpoint.call_count == fetches + 1

    def test_valid_access_token_is_kept(self, wikibase, token_endpoint):
        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        fetches = token_endpoint.call_count

        read(login)
        read(login)
        assert token_endpoint.call_count == fetches

    def test_access_token_without_expiry_is_kept(self, wikibase, requests_mock):
        endpoint = requests_mock.post(wikibase.mediawiki_rest_url + '/oauth2/access_token', json={'access_token': 'oauth2-access-token', 'token_type': 'Bearer'})
        login = wbi_login.OAuth2(consumer_token='consumer-token', consumer_secret='consumer-secret')
        fetches = endpoint.call_count

        read(login)
        assert endpoint.call_count == fetches
