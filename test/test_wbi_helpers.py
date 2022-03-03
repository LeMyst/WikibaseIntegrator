import logging
import unittest

import requests

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import MWApiError
from wikibaseintegrator.wbi_helpers import execute_sparql_query, get_user_agent, mediawiki_api_call_helper


def test_connection():
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    data = {'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}

    mediawiki_api_call_helper(data=data, max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/500", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/502", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/503", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/504", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(requests.HTTPError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/400", max_retries=2, retry_after=1, allow_anonymous=True)


def test_user_agent(caplog):
    wbi_config['USER_AGENT'] = None  # Reset user agent
    # Test there is no warning because of the user agent
    with caplog.at_level(logging.WARNING):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True,
                                  user_agent='MyWikibaseBot/0.5')
    assert 'WARNING' not in caplog.text

    # Test there is a warning
    with caplog.at_level(logging.WARNING):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True)
    assert 'Please set an user agent' in caplog.text

    # Test if the user agent is correctly added
    new_user_agent = get_user_agent(user_agent='MyWikibaseBot/0.5')
    assert new_user_agent.startswith('MyWikibaseBot/0.5')
    assert 'WikibaseIntegrator' in new_user_agent


def test_allow_anonymous():
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    # Test there is a warning because of allow_anonymous
    with unittest.TestCase().assertRaises(ValueError):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, user_agent='MyWikibaseBot/0.5')

    # Test there is no warning because of allow_anonymous
    assert mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True,
                                     user_agent='MyWikibaseBot/0.5')


def test_sparql():
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    results = execute_sparql_query('''SELECT ?child ?childLabel
WHERE
{
# ?child  father   Bach
  ?child wdt:P22 wd:Q1339.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE]". }
}''')
    assert len(results['results']['bindings']) > 1
