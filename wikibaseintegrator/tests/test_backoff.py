import unittest
import requests
import sys

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
pyv = sys.version_info.major
if pyv == 3:
    import json
else:
    import simplejson as json


class TestMethods(unittest.TestCase):
    def test_all(self):
        config['BACKOFF_MAX_TRIES'] = 2
        config['BACKOFF_MAX_VALUE'] = 2
        with self.assertRaises(requests.RequestException):
            bad_http_code()
        with self.assertRaises(requests.RequestException):
            bad_login()

        assert good_http_code() == "200 OK"

        with self.assertRaises(json.JSONDecodeError):
            bad_json()


@wbi_backoff()
def bad_http_code():
    r = requests.get("http://httpstat.us/400")
    r.raise_for_status()
    print(r.text)


@wbi_backoff()
def good_http_code():
    r = requests.get("http://httpstat.us/200")
    r.raise_for_status()
    print(r.text)
    return r.text


@wbi_backoff()
def bad_json():
    json.loads("<xml>I failed :(</xml>")


@wbi_backoff()
def bad_request():
    requests.get("http://www.fakeurlgsdkjhjgfseg.com")


def bad_login():
    wbi_login.WDLogin("name", "pass", mediawiki_api_url="www.wikidataaaaaaaaa.org")


if __name__ == "__main__":
    if sys.argv[1] == "json":
        bad_json()
    if sys.argv[1] == "request":
        bad_request()
    if sys.argv[1] == "login":
        bad_login()
    if sys.argv[1] == "badcode":
        bad_http_code()
    if sys.argv[1] == "goodcode":
        good_http_code()
