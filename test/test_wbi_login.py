import os
import sys
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
import requests
from oauthlib.oauth2 import MissingTokenError

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper
# look for environment variables. if none set, don't do anything
from wikibaseintegrator.wbi_login import LoginError

WDUSER = os.getenv("WDUSER")
WDPASS = os.getenv("WDPASS")
OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY = os.getenv("OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY")
OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY = os.getenv("OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY")
OAUTH1_CONSUMER_TOKEN = os.getenv("OAUTH1_CONSUMER_TOKEN")
OAUTH1_CONSUMER_SECRET = os.getenv("OAUTH1_CONSUMER_SECRET")
OAUTH1_ACCESS_TOKEN = os.getenv("OAUTH1_ACCESS_TOKEN")
OAUTH1_ACCESS_SECRET = os.getenv("OAUTH1_ACCESS_SECRET")
OAUTH2_CONSUMER_TOKEN = os.getenv("OAUTH2_CONSUMER_TOKEN")
OAUTH2_CONSUMER_SECRET = os.getenv("OAUTH2_CONSUMER_SECRET")


class _FakeResponse:
    def __init__(self, payload=None, json_exception=None):
        self._payload = payload or {}
        self._json_exception = json_exception

    def json(self):
        if self._json_exception:
            raise self._json_exception
        return self._payload


def test_login():
    def fake_post(*args, **kwargs):
        data = kwargs.get('data', {})
        if data.get('type') == 'login':
            return _FakeResponse({'query': {'tokens': {'logintoken': 'token'}}})
        if data.get('action') == 'clientlogin':
            return _FakeResponse({'clientlogin': {'status': 'FAIL', 'messagecode': 'mock-fail', 'message': 'mock failure'}})
        if data.get('action') == 'login':
            return _FakeResponse({'login': {'result': 'Failed', 'reason': 'mock failure'}})
        return _FakeResponse({'query': {'tokens': {'csrftoken': '+\\'}}})

    with patch('wikibaseintegrator.wbi_login.Session.post', side_effect=fake_post):
        with pytest.raises(LoginError):
            login = wbi_login.Clientlogin(user='wrong', password='wrong')
            login.generate_edit_credentials()

        with pytest.raises(LoginError):
            login = wbi_login.Login(user='wrong', password='wrong')
            login.generate_edit_credentials()

    if WDUSER and WDPASS:
        assert wbi_login.Clientlogin(user=WDUSER, password=WDPASS)
        assert wbi_login.Login(user=WDUSER, password=WDPASS)
    else:
        print("no WDUSER or WDPASS found in environment variables", file=sys.stderr)


def test_verify():
    def fake_post(url, *args, **kwargs):
        if urlparse(url).hostname == 'self-signed.badssl.com':
            if kwargs.get('verify', True):
                raise requests.exceptions.SSLError('mock ssl error')
            return _FakeResponse(json_exception=requests.exceptions.JSONDecodeError('mock json error', 'x', 0))
        return _FakeResponse({'query': {'tokens': {'logintoken': 'token'}}})

    with patch('wikibaseintegrator.wbi_login.Session.post', side_effect=fake_post):
        with pytest.raises(requests.exceptions.SSLError):
            wbi_login.Clientlogin(user='wrong', password='wrong', mediawiki_api_url='https://self-signed.badssl.com/', verify=True)

        with pytest.raises(requests.exceptions.JSONDecodeError):
            wbi_login.Clientlogin(user='wrong', password='wrong', mediawiki_api_url='https://self-signed.badssl.com/', verify=False)


def test_oauth1():
    with patch('wikibaseintegrator.wbi_login.Handshaker.initiate', side_effect=wbi_login.OAuthException('mock oauth1 failure')):
        with pytest.raises(LoginError):
            login = wbi_login.OAuth1(consumer_token='wrong', consumer_secret='wrong')
            login.generate_edit_credentials()

    if OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY and OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY:
        wbi_login.OAuth1(consumer_token=OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY, consumer_secret=OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY)
    else:
        print("no OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY or OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY found in environment variables", file=sys.stderr)


def test_oauth1_access():
    with patch('wikibaseintegrator.wbi_login._Login.generate_edit_credentials', side_effect=LoginError('mock oauth1 access failure')):
        with pytest.raises(LoginError):
            login = wbi_login.OAuth1(consumer_token='wrong', consumer_secret='wrong', access_token='wrong', access_secret='wrong')
            login.generate_edit_credentials()

    if OAUTH1_CONSUMER_TOKEN and OAUTH1_CONSUMER_SECRET and OAUTH1_ACCESS_TOKEN and OAUTH1_ACCESS_SECRET:
        login = wbi_login.OAuth1(consumer_token=OAUTH1_CONSUMER_TOKEN, consumer_secret=OAUTH1_CONSUMER_SECRET, access_token=OAUTH1_ACCESS_TOKEN, access_secret=OAUTH1_ACCESS_SECRET)
        login.generate_edit_credentials()
    else:
        print("no OAUTH1_CONSUMER_TOKEN or OAUTH1_CONSUMER_SECRET or OAUTH1_ACCESS_TOKEN or OAUTH1_ACCESS_SECRET found in environment variables", file=sys.stderr)


def test_oauth2():
    with patch('wikibaseintegrator.wbi_login.OAuth2Session.fetch_token', side_effect=MissingTokenError('mock oauth2 failure')):
        with pytest.raises((MissingTokenError, LoginError)):
            login = wbi_login.OAuth2(consumer_token='wrong', consumer_secret='wrong')
            login.generate_edit_credentials()

    if OAUTH2_CONSUMER_TOKEN and OAUTH2_CONSUMER_SECRET:
        login = wbi_login.OAuth2(consumer_token=OAUTH2_CONSUMER_TOKEN, consumer_secret=OAUTH2_CONSUMER_SECRET)
        login.generate_edit_credentials()
    else:
        print("no OAUTH2_CONSUMER_TOKEN or CLIENT_SECRET found in environment variables", file=sys.stderr)


def test_mismatch_api_url():
    if WDUSER and WDPASS:
        login = wbi_login.Login(user=WDUSER, password=WDPASS)
        login.generate_edit_credentials()
        with pytest.raises(ValueError):
            mediawiki_api_call_helper(data={}, login=login, mediawiki_api_url='https://unsdfdskfjljzkerezr.org/w/api.php')
