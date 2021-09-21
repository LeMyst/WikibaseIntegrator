import unittest

import requests

from wikibaseintegrator.wbi_exceptions import MWApiError
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper, get_user_agent, execute_sparql_query


def test_connection():
    with unittest.TestCase().assertRaises(MWApiError):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=3,
                                  retry_after=1, allow_anonymous=True)
    with unittest.TestCase().assertRaises(requests.HTTPError):
        mediawiki_api_call_helper(data=None, mediawiki_api_url="https://httpbin.org/status/400", max_retries=3, retry_after=1, allow_anonymous=True)

    mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True)


def test_user_agent(capfd):
    # Test there is a warning
    mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True)
    out, err = capfd.readouterr()
    assert out

    # Test there is no warning because of the user agent
    mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True, user_agent='MyWikibaseBot/0.5')
    out, err = capfd.readouterr()
    assert not out

    # Test if the user agent is correctly added
    new_user_agent = get_user_agent(user_agent='MyWikibaseBot/0.5')
    assert new_user_agent.startswith('MyWikibaseBot/0.5')
    assert 'WikibaseIntegrator' in new_user_agent


def test_allow_anonymous():
    # Test there is a warning because of allow_anonymous
    with unittest.TestCase().assertRaises(ValueError):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, user_agent='MyWikibaseBot/0.5')

    # Test there is no warning because of allow_anonymous
    assert mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True,
                                     user_agent='MyWikibaseBot/0.5')


def test_sparql():
    results = execute_sparql_query('''SELECT ?child ?childLabel
WHERE
{
# ?child  father   Bach
  ?child wdt:P22 wd:Q1339.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE]". }
}''')
    assert len(results['results']['bindings']) > 1
