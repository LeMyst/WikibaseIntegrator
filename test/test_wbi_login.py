from __future__ import print_function

import os
import sys

import pytest

from wikibaseintegrator import wbi_login, wbi_core

# look for environment variables. if none set, don't do anything
WDUSER = os.getenv("WDUSER")
WDPASS = os.getenv("WDPASS")


def test_login():
    if WDUSER and WDPASS:
        wbi_login.Login(WDUSER, WDPASS)
    else:
        print("no WDUSER or WDPASS found in environment variables", file=sys.stderr)


def test_write():
    if WDUSER and WDPASS:
        login = wbi_login.Login(WDUSER, WDPASS)
        with pytest.raises(ValueError):
            wbi_core.FunctionsEngine.mediawiki_api_call_helper(data=None, login=login, mediawiki_api_url='http://unsdfdskfjljzkerezr.org/w/api.php')
