import os
import unittest
from unittest.mock import patch

import requests
import ujson

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config


class TestMethods(unittest.TestCase):
    def test_all(self):
        def fake_get(url, *args, **kwargs):
            del args, kwargs

            class _FakeResponse:
                def __init__(self, status_code):
                    self.status_code = status_code

                def raise_for_status(self):
                    if self.status_code >= 400:
                        raise requests.HTTPError(f'mock {self.status_code}')

            if '/status/400' in url:
                return _FakeResponse(400)
            if '/status/200' in url:
                return _FakeResponse(200)
            raise requests.ConnectionError('mock connection error')

        config['BACKOFF_MAX_TRIES'] = 2
        config['BACKOFF_MAX_VALUE'] = 3
        with patch('requests.get', side_effect=fake_get), patch('wikibaseintegrator.wbi_login.Clientlogin', side_effect=requests.RequestException('mock login error')):
            with self.assertRaises(requests.RequestException):
                bad_http_code()
            with self.assertRaises(requests.RequestException):
                bad_login()
            with self.assertRaises(requests.RequestException):
                bad_request()

            assert good_http_code() == 200

            with self.assertRaises(ValueError):
                bad_json()


# @backoff.on_exception(backoff.expo, (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.HTTPError, JSONDecodeError), max_time=60)

@wbi_backoff()
def bad_http_code():
    r = requests.get(os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/400")
    r.raise_for_status()


@wbi_backoff()
def good_http_code():
    r = requests.get(os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/200")
    r.raise_for_status()
    print(r.status_code)
    return r.status_code


@wbi_backoff()
def bad_json():
    ujson.loads("<xml>I failed :(</xml>")


@wbi_backoff()
def bad_request():
    requests.get("https://www.fakeurlgsdkjhjgfseg.com")


def bad_login():
    wbi_login.Clientlogin(user='name', password='pass', mediawiki_api_url="www.wikidataaaaaaaaa.org")
