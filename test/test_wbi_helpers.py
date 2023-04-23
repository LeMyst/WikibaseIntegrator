import logging
import unittest

import requests

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import MaxRetriesReachedException
from wikibaseintegrator.wbi_helpers import execute_sparql_query, format2wbi, get_user_agent, mediawiki_api_call_helper


def test_connection():
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    data = {'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}

    mediawiki_api_call_helper(data=data, max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/500", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/502", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://httpbin.org/status/503", max_retries=2, retry_after=1, allow_anonymous=True)

    with unittest.TestCase().assertRaises(MaxRetriesReachedException):
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


def test_format2wbi():
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity

    assert isinstance(format2wbi('item', '{}'), ItemEntity)
    assert isinstance(format2wbi('property', '{}'), PropertyEntity)
    assert isinstance(format2wbi('lexeme', '{}'), LexemeEntity)
    assert isinstance(format2wbi('mediainfo', '{}'), MediaInfoEntity)
    with unittest.TestCase().assertRaises(ValueError):
        format2wbi('unknown', '{}')

    result = format2wbi('item', '''{
  "aliases": {
    "uk": "Війєрбан",
    "be": [
      {
        "value": "Вілербан"
      },
      {
        "value": "Віербан"
      }
    ],
    "en": [
      "first alias",
      "second alias"
    ]
  },
  "labels": {
    "en": "Between Expressiveness and Verifiability: P/T-nets with Synchronous Channels and Modular Structure"
  },
  "descriptions": {
    "en": "scientific paper published in CEUR-WS Volume 3170"
  },
  "claims": {
    "P1433": "Q113529188",
    "P1476": {
      "text": "Between Expressiveness and Verifiability: P/T-nets with Synchronous Channels and Modular Structure",
      "language": "en"
    },
    "P2093": [
      {
        "value": "Lukas Voß",
        "qualifiers": {
          "P1545": "1"
        }
      },
      {
        "value": "Sven Willrodt",
        "qualifiers": {
          "P1545": "2"
        }
      },
      {
        "value": "Daniel Moldt",
        "qualifiers": {
          "P1545": "3"
        }
      },
      {
        "value": "Michael Haustermann",
        "qualifiers": {
          "P1545": "4"
        }
      }
    ],
    "P31": "Q13442814",
    "P407": "Q1860",
    "P50": [],
    "P953": "https://ceur-ws.org/Vol-3170/paper3.pdf"
  }
}''')
    assert isinstance(result, ItemEntity)

    # Test aliases
    # TODO: add test aliases

    # Test descriptions
    assert result.descriptions.get('en') == 'scientific paper published in CEUR-WS Volume 3170'

    # Test labels
    assert result.labels.get('en') == 'Between Expressiveness and Verifiability: P/T-nets with Synchronous Channels and Modular Structure'
