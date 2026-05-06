import logging
import os

import pytest
import requests

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import MaxRetriesReachedException
from wikibaseintegrator.wbi_helpers import execute_sparql_query, format2wbi, get_user_agent, mediawiki_api_call_helper


def _fake_mediawiki_call(data, mediawiki_api_url=None, **kwargs):
    url = mediawiki_api_url or ''
    if 'wikidataaaaaaa.org' in url:
        raise MaxRetriesReachedException('mock connection failure')
    if '/status/500' in url or '/status/502' in url or '/status/503' in url or '/status/504' in url:
        raise MaxRetriesReachedException('mock retry exhausted')
    if '/status/400' in url:
        raise requests.HTTPError('mock 400')

    if data.get('action') == 'wbgetentities' and data.get('props') == 'datatype':
        datatype_map = {
            'P1433': 'wikibase-item',
            'P1476': 'monolingualtext',
            'P2093': 'string',
            'P31': 'wikibase-item',
            'P407': 'wikibase-item',
            'P50': 'wikibase-item',
            'P953': 'url',
            'P1545': 'string',
        }
        ids = str(data.get('ids', '')).split('|')
        return {'entities': {prop: {'datatype': datatype_map.get(prop, 'string')} for prop in ids}}

    return {'success': 1, 'entities': {'Q42': {'id': 'Q42'}}}


def test_connection(monkeypatch):
    monkeypatch.setattr('test.test_wbi_helpers.mediawiki_api_call_helper', _fake_mediawiki_call)
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    data = {'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}

    mediawiki_api_call_helper(data=data, max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/500", max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/502", max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/503", max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(MaxRetriesReachedException):
        mediawiki_api_call_helper(data=data, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/504", max_retries=2, retry_after=1, allow_anonymous=True)

    with pytest.raises(requests.HTTPError):
        mediawiki_api_call_helper(data=data, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/400", max_retries=2, retry_after=1, allow_anonymous=True)


def test_user_agent(caplog):
    from wikibaseintegrator import wbi_helpers
    wbi_helpers.mediawiki_api_call = lambda *args, **kwargs: {'success': 1}

    wbi_config['MEDIAWIKI_API_URL'] = 'https://www.wikidata.org/w/api.php'
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

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        mediawiki_api_call_helper(
            data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'},
            mediawiki_api_url='https://www.wikidataaaaaaa.org/w/api.php',
            max_retries=3,
            retry_after=1,
            allow_anonymous=True,
        )
    assert 'Please set an user agent' not in caplog.text

    # Test if the user agent is correctly added
    new_user_agent = get_user_agent(user_agent='MyWikibaseBot/0.5')
    assert new_user_agent.startswith('MyWikibaseBot/0.5')
    assert 'WikibaseIntegrator' in new_user_agent


def test_allow_anonymous():
    from wikibaseintegrator import wbi_helpers
    wbi_helpers.mediawiki_api_call = lambda *args, **kwargs: {'success': 1}

    wbi_config['MEDIAWIKI_API_URL'] = 'https://www.wikidata.org/w/api.php'
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    # Test there is a warning because of allow_anonymous
    with pytest.raises(ValueError):
        mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, user_agent='MyWikibaseBot/0.5')

    # Test there is no warning because of allow_anonymous
    assert mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1, allow_anonymous=True,
                                     user_agent='MyWikibaseBot/0.5')


def test_sparql(monkeypatch):
    monkeypatch.setattr(
        'test.test_wbi_helpers.execute_sparql_query',
        lambda *_args, **_kwargs: {'results': {'bindings': [{'child': {'value': 'Q1'}}, {'child': {'value': 'Q2'}}]}},
    )
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    results = execute_sparql_query('''SELECT ?child ?childLabel
WHERE
{
# ?child  father   Bach
  ?child wdt:P22 wd:Q1339.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE]". }
}''')
    assert len(results['results']['bindings']) > 1


def test_format2wbi(monkeypatch):
    monkeypatch.setattr('wikibaseintegrator.wbi_helpers.mediawiki_api_call_helper', _fake_mediawiki_call)
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_helpers.py)'
    from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity

    assert isinstance(format2wbi('item', '{}'), ItemEntity)
    assert isinstance(format2wbi('property', '{}'), PropertyEntity)
    assert isinstance(format2wbi('lexeme', '{}'), LexemeEntity)
    assert isinstance(format2wbi('mediainfo', '{}'), MediaInfoEntity)
    with pytest.raises(ValueError):
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
