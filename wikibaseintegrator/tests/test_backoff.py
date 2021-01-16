import sys
import unittest

import requests

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
import json


class TestMethods(unittest.TestCase):
    def test_all(self):
        config['BACKOFF_MAX_TRIES'] = 2
        config['BACKOFF_MAX_VALUE'] = 2
        with self.assertRaises(requests.RequestException):
            bad_http_code()
        with self.assertRaises(requests.RequestException):
            bad_login()
        with self.assertRaises(requests.RequestException):
            bad_request()

        assert good_http_code() == 200

        with self.assertRaises(json.JSONDecodeError):
            bad_json()


@wbi_backoff()
def bad_http_code():
    r = requests.get("http://httpbin.org/status/400")
    r.raise_for_status()

@wbi_backoff()
def good_http_code():
    r = requests.get("http://httpbin.org/status/200")
    r.raise_for_status()
    print(r.status_code)
    return r.status_code


@wbi_backoff()
def bad_json():
    json.loads("<xml>I failed :(</xml>")


@wbi_backoff()
def bad_request():
    requests.get("http://www.fakeurlgsdkjhjgfseg.com")


def bad_login():
    wbi_login.Login("name", "pass", mediawiki_api_url="www.wikidataaaaaaaaa.org")
