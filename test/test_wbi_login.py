import os
import sys
import unittest

import pytest

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


def test_login():
    with unittest.TestCase().assertRaises(LoginError):
        login = wbi_login.Clientlogin(user='wrong', password='wrong')
        login.generate_edit_credentials()

    with unittest.TestCase().assertRaises(LoginError):
        login = wbi_login.Login(user='wrong', password='wrong')
        login.generate_edit_credentials()

    if WDUSER and WDPASS:
        assert wbi_login.Clientlogin(user=WDUSER, password=WDPASS)
        assert wbi_login.Login(user=WDUSER, password=WDPASS)
    else:
        print("no WDUSER or WDPASS found in environment variables", file=sys.stderr)


def test_oauth1():
    with unittest.TestCase().assertRaises(LoginError):
        login = wbi_login.OAuth1(consumer_token='wrong', consumer_secret='wrong')
        login.generate_edit_credentials()

    if OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY and OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY:
        wbi_login.OAuth1(consumer_token=OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY, consumer_secret=OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY)
    else:
        print("no OAUTH1_CONSUMER_TOKEN_NOT_OWNER_ONLY or OAUTH1_CONSUMER_SECRET_NOT_OWNER_ONLY found in environment variables", file=sys.stderr)


def test_oauth1_access():
    with unittest.TestCase().assertRaises(LoginError):
        login = wbi_login.OAuth1(consumer_token='wrong', consumer_secret='wrong', access_token='wrong', access_secret='wrong')
        login.generate_edit_credentials()

    if OAUTH1_CONSUMER_TOKEN and OAUTH1_CONSUMER_SECRET and OAUTH1_ACCESS_TOKEN and OAUTH1_ACCESS_SECRET:
        login = wbi_login.OAuth1(consumer_token=OAUTH1_CONSUMER_TOKEN, consumer_secret=OAUTH1_CONSUMER_SECRET, access_token=OAUTH1_ACCESS_TOKEN, access_secret=OAUTH1_ACCESS_SECRET)
        login.generate_edit_credentials()
    else:
        print("no OAUTH1_CONSUMER_TOKEN or OAUTH1_CONSUMER_SECRET or OAUTH1_ACCESS_TOKEN or OAUTH1_ACCESS_SECRET found in environment variables", file=sys.stderr)


def test_oauth2():
    with unittest.TestCase().assertRaises(LoginError):
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
