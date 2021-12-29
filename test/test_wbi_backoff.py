import unittest

import requests
import ujson

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config


class TestMethods(unittest.TestCase):
    def test_all(self):
        config['BACKOFF_MAX_TRIES'] = 1
        config['BACKOFF_MAX_VALUE'] = 2
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
    r = requests.get("https://httpbin.org/status/400")
    r.raise_for_status()


@wbi_backoff()
def good_http_code():
    r = requests.get("https://httpbin.org/status/200")
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
