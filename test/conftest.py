"""
Test harness for WikibaseIntegrator.

Every unit test runs fully offline: all HTTP traffic issued through the
`requests` library is intercepted by `requests-mock` and served by
:class:`MockWikibase`, a small in-memory emulation of the MediaWiki/Wikibase
action API backed by the JSON fixtures stored in ``test/fixtures/``.

Guidelines:
- Request the ``wikibase`` fixture to interact with a simulated Wikibase
  instance (reads, writes, login, SPARQL). The fixture also points the
  wbi_config URLs to the simulated instance.
- Use ``wikibase.add_fixture('item_Q582')`` (or ``add_entity``/``add_property``)
  to populate the instance.
- After a write, inspect ``wikibase.edits`` to assert exactly what the library
  sent over the wire.
- For low-level HTTP behaviour (5xx, maxlag, malformed payloads...), use the
  ``requests_mock`` fixture directly.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock as requests_mock_lib

from wikibaseintegrator import wbi_fastrun, wbi_helpers
from wikibaseintegrator.wbi_config import config as wbi_config

FIXTURE_DIR = Path(__file__).parent / 'fixtures'

ENTITY_PREFIXES = {
    'item': 'Q',
    'property': 'P',
    'lexeme': 'L',
    'mediainfo': 'M',
}

# Entity sections that can be filtered with the 'props' API parameter.
ENTITY_SECTIONS = {'labels', 'descriptions', 'aliases', 'claims', 'statements', 'sitelinks', 'lemmas', 'forms', 'senses'}


def load_fixture(name: str) -> dict:
    """Load a JSON fixture from test/fixtures/ and return a fresh copy of it."""
    with open(FIXTURE_DIR / f'{name}.json', encoding='utf-8') as f:
        return json.load(f)


class MockWikibase:
    """
    In-memory emulation of the subset of the MediaWiki/Wikibase action API and
    of the SPARQL endpoint used by WikibaseIntegrator.

    The emulation is deliberately small but faithful: responses reuse the JSON
    shapes produced by a real Wikibase instance so that the (de)serialization
    code of the library is exercised exactly as in production.
    """

    def __init__(self, mocker: requests_mock_lib.Mocker, base_url: str = 'https://wikibase.example.org'):
        self.base_url = base_url
        self.mediawiki_api_url = base_url + '/w/api.php'
        self.mediawiki_index_url = base_url + '/w/index.php'
        self.mediawiki_rest_url = base_url + '/w/rest.php'
        self.sparql_endpoint_url = base_url + '/sparql'

        self.entities: dict[str, dict] = {}
        self.next_entity_id = 100000

        # Recorded traffic, for assertions in tests
        self.requests: list[dict[str, str]] = []  # every parsed API request
        self.edits: list[dict[str, Any]] = []  # every wbeditentity call: {'params': ..., 'data': ...}
        self.sparql_queries: list[str] = []

        # Configurable behaviour
        self.search_results: list[dict] = []  # wbsearchentities results
        self.fulltext_results: list[dict] = []  # list=search results
        self.sparql_bindings: list[dict] = []  # bindings returned by the SPARQL endpoint
        self.valid_credentials: dict[str, str] = {}  # user -> password accepted by (client)login
        self.login_token = 'aabbccddeeff+\\'
        self.csrf_token = '0123456789abcdef+\\'
        self._forced_errors: list[dict] = []

        mocker.register_uri(requests_mock_lib.ANY, self.mediawiki_api_url, json=self._handle_api)
        mocker.post(self.sparql_endpoint_url, json=self._handle_sparql)

    # ------------------------------------------------------------------ #
    # Content setup helpers
    # ------------------------------------------------------------------ #

    def add_entity(self, entity: dict) -> dict:
        """Register an entity (raw Wikibase JSON) on the simulated instance."""
        self.entities[entity['id']] = deepcopy(entity)
        return entity

    def add_fixture(self, name: str) -> dict:
        """Load a fixture file and register it on the simulated instance."""
        return self.add_entity(load_fixture(name))

    def add_property(self, prop_nr: str, datatype: str, label: str = 'a property') -> dict:
        """Register a minimal property entity, mostly used for datatype lookups."""
        return self.add_entity({
            'pageid': 1000 + int(prop_nr[1:]),
            'ns': 120,
            'title': f'Property:{prop_nr}',
            'lastrevid': 1,
            'type': 'property',
            'datatype': datatype,
            'id': prop_nr,
            'labels': {'en': {'language': 'en', 'value': label}},
            'descriptions': {},
            'aliases': {},
            'claims': {},
        })

    def fail_next(self, code: str, info: str = 'Simulated error.', **extra: Any) -> None:
        """Make the next API call return the given MediaWiki error payload."""
        self._forced_errors.append({'code': code, 'info': info, **extra})

    # ------------------------------------------------------------------ #
    # Introspection helpers
    # ------------------------------------------------------------------ #

    @property
    def last_request(self) -> dict[str, str]:
        return self.requests[-1]

    @property
    def last_edit(self) -> dict[str, Any]:
        return self.edits[-1]

    # ------------------------------------------------------------------ #
    # Request handling
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_params(request: Any) -> dict[str, str]:
        params = {key: values[0] for key, values in parse_qs(urlparse(request.url).query, keep_blank_values=True).items()}
        if request.method == 'POST' and request.text:
            params.update({key: values[0] for key, values in parse_qs(request.text, keep_blank_values=True).items()})
        return params

    def _handle_api(self, request: Any, context: Any) -> dict:
        params = self._parse_params(request)
        self.requests.append(params)

        if self._forced_errors:
            return {'error': self._forced_errors.pop(0), 'servedby': 'mock'}

        action = params.get('action', '')
        handler = getattr(self, f'_action_{action}', None)
        if handler is None:
            return {'error': {'code': 'unknown_action', 'info': f'Unrecognized value for parameter "action": {action}.'}}

        return handler(params)

    def _handle_sparql(self, request: Any, context: Any) -> dict:
        params = parse_qs(urlparse(request.url).query, keep_blank_values=True)
        # The query is sent in the request body (form-encoded), fall back to the URL query string for robustness.
        if request.method == 'POST' and request.text:
            params.update(parse_qs(request.text, keep_blank_values=True))
        query = params.get('query', [''])[0]
        self.sparql_queries.append(query)

        bindings = self.sparql_bindings
        if callable(bindings):
            bindings = bindings(query)

        return {
            'head': {'vars': ['sid', 'item', 'v', 'unit', 'pq', 'qval', 'qunit', 'ref', 'pr', 'rval', 'label']},
            'results': {'bindings': bindings},
        }

    # ------------------------------------------------------------------ #
    # action= handlers
    # ------------------------------------------------------------------ #

    def _action_wbgetentities(self, params: dict[str, str]) -> dict:
        if 'titles' in params:
            titles = params['titles'].split('|')
            found = {entity_id: deepcopy(entity) for entity_id, entity in self.entities.items() if entity.get('title') in titles}
            return {'entities': found, 'success': 1}

        entities = {}
        for entity_id in params['ids'].split('|'):
            if entity_id not in self.entities:
                return {
                    'error': {
                        'code': 'no-such-entity',
                        'info': f'Could not find an entity with the ID "{entity_id}".',
                        'id': entity_id,
                        'messages': [{'name': 'wikibase-api-no-such-entity', 'parameters': [], 'html': {'*': 'Could not find an entity with the ID.'}}],
                    },
                    'servedby': 'mock',
                }
            entities[entity_id] = self._project(self.entities[entity_id], params.get('props'))

        return {'entities': entities, 'success': 1}

    @staticmethod
    def _project(entity: dict, props: str | None) -> dict:
        """Apply the 'props' parameter filtering, like the real API does."""
        if props is None:
            return deepcopy(entity)

        keep = set(props.split('|'))
        if 'claims' in keep:
            keep.add('statements')

        return {key: deepcopy(value) for key, value in entity.items() if key not in ENTITY_SECTIONS or key in keep}

    def _action_wbeditentity(self, params: dict[str, str]) -> dict:
        data = json.loads(params['data'])
        self.edits.append({'params': params, 'data': data})

        if params.get('id'):
            entity_id = params['id']
            base = deepcopy(self.entities.get(entity_id, {}))
            entity_type = base.get('type', 'item')
        else:
            entity_type = params['new']
            entity_id = f'{ENTITY_PREFIXES[entity_type]}{self.next_entity_id}'
            self.next_entity_id += 1
            base = {}

        if 'clear' in params:
            base = {key: value for key, value in base.items() if key not in ENTITY_SECTIONS}

        entity = self._apply_edit(base, data, entity_id, entity_type)
        self.entities[entity_id] = deepcopy(entity)

        return {'entity': entity, 'success': 1}

    def _apply_edit(self, base: dict, data: dict, entity_id: str, entity_type: str) -> dict:
        entity = base or {'type': entity_type, 'ns': 0, 'title': entity_id, 'pageid': self.next_entity_id, 'lastrevid': 0}
        entity['id'] = entity_id
        entity['type'] = entity.get('type', entity_type)
        entity['lastrevid'] = entity.get('lastrevid', 0) + 1

        # Language values (labels, descriptions): honor the 'remove' marker.
        for section in ('labels', 'descriptions'):
            if section in data:
                target = entity.setdefault(section, {})
                for language, value in data[section].items():
                    if 'remove' in value:
                        target.pop(language, None)
                    else:
                        target[language] = {'language': value['language'], 'value': value['value']}

        if 'aliases' in data:
            target = entity.setdefault('aliases', {})
            for language, values in data['aliases'].items():
                kept = [{'language': alias['language'], 'value': alias['value']} for alias in values if 'remove' not in alias]
                if kept:
                    target[language] = kept
                else:
                    target.pop(language, None)

        if 'sitelinks' in data:
            target = entity.setdefault('sitelinks', {})
            for site, sitelink in data['sitelinks'].items():
                if 'remove' in sitelink or not sitelink.get('title'):
                    target.pop(site, None)
                else:
                    target[site] = {'site': sitelink['site'], 'title': sitelink['title'], 'badges': sitelink.get('badges', [])}

        claims_key = 'statements' if entity_type == 'mediainfo' else 'claims'
        for key in ('claims', 'statements'):
            if key in data:
                entity[claims_key] = self._apply_claims(entity.get(claims_key, {}), data[key], entity_id)

        # Lexeme specific sections, stored as-is.
        for section in ('lemmas', 'lexicalCategory', 'language', 'forms', 'senses'):
            if section in data:
                entity[section] = deepcopy(data[section])

        if entity_type == 'property' and 'datatype' in data:
            entity['datatype'] = data['datatype']

        return entity

    def _apply_claims(self, current: dict, submitted: dict | list, entity_id: str) -> dict:
        """Merge submitted claims into the current ones, like wbeditentity does."""
        result = deepcopy(current)

        if isinstance(submitted, dict):
            submitted = [claim for statements in submitted.values() for claim in statements]

        for claim in submitted:
            if 'remove' in claim:
                for prop_nr, statements in list(result.items()):
                    result[prop_nr] = [statement for statement in statements if statement.get('id') != claim.get('id')]
                    if not result[prop_nr]:
                        del result[prop_nr]
                continue

            claim = deepcopy(claim)
            prop_nr = claim['mainsnak']['property']
            statements = result.setdefault(prop_nr, [])

            # A real instance computes a hash for every reference block; the
            # client never sends one and the deserializer requires it.
            for position, reference in enumerate(claim.get('references', [])):
                reference.setdefault('hash', f'mockhash{position:040d}'[-40:])

            if claim.get('id'):
                for position, statement in enumerate(statements):
                    if statement.get('id') == claim['id']:
                        statements[position] = claim
                        break
                else:
                    statements.append(claim)
            else:
                # A real instance assigns a GUID to new statements.
                claim['id'] = f'{entity_id}$mock-{len(self.requests)}-{len(statements)}'
                statements.append(claim)

        return result

    def _action_query(self, params: dict[str, str]) -> dict:
        if params.get('meta') == 'tokens':
            if params.get('type') == 'login':
                return {'batchcomplete': '', 'query': {'tokens': {'logintoken': self.login_token}}}
            return {'batchcomplete': '', 'query': {'tokens': {'csrftoken': self.csrf_token}}}

        if params.get('list') == 'search':
            return {'batchcomplete': '', 'query': {'searchinfo': {'totalhits': len(self.fulltext_results)}, 'search': deepcopy(self.fulltext_results)}}

        return {'batchcomplete': ''}

    def _action_login(self, params: dict[str, str]) -> dict:
        if params.get('lgtoken') != self.login_token:
            return {'login': {'result': 'WrongToken'}}

        user = params.get('lgname', '')
        if self.valid_credentials.get(user) == params.get('lgpassword'):
            return {'login': {'result': 'Success', 'lgusername': user, 'lguserid': 1}}

        return {'login': {'result': 'Failed', 'reason': 'Incorrect username or password entered. Please try again.'}}

    def _action_clientlogin(self, params: dict[str, str]) -> dict:
        user = params.get('username', '')
        if self.valid_credentials.get(user) == params.get('password'):
            return {'clientlogin': {'status': 'PASS', 'username': user}}

        return {'clientlogin': {'status': 'FAIL', 'message': 'Incorrect username or password entered. Please try again.', 'messagecode': 'wrongpassword'}}

    def _action_wbsearchentities(self, params: dict[str, str]) -> dict:
        offset = int(params.get('continue', 0))
        limit = int(params.get('limit', 50))
        page = deepcopy(self.search_results[offset:offset + limit])

        response: dict[str, Any] = {'searchinfo': {'search': params['search']}, 'search': page, 'success': 1}
        if offset + limit < len(self.search_results):
            response['search-continue'] = offset + limit

        return response

    def _action_wbmergeitems(self, params: dict[str, str]) -> dict:
        return {'success': 1, 'redirected': 1, 'from': {'id': params['fromid']}, 'to': {'id': params['toid']}}

    def _action_wbremoveclaims(self, params: dict[str, str]) -> dict:
        return {'pageinfo': {'lastrevid': 1}, 'success': 1, 'claims': params['claim'].split('|')}

    def _action_delete(self, params: dict[str, str]) -> dict:
        return {'delete': {'title': params.get('title', ''), 'reason': params.get('reason', 'mock deletion'), 'logid': 1}}


# ---------------------------------------------------------------------- #
# SPARQL helpers usable from the tests
# ---------------------------------------------------------------------- #

def uri(value: str) -> dict:
    return {'type': 'uri', 'value': value}


def literal(value: str, datatype: str | None = None, lang: str | None = None) -> dict:
    binding = {'type': 'literal', 'value': value}
    if datatype:
        binding['datatype'] = datatype
    if lang:
        binding['xml:lang'] = lang
    return binding


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def preserve_config():
    """Isolate each test from wbi_config mutations made by other tests."""
    original = deepcopy(wbi_config)
    wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0'
    yield wbi_config
    wbi_config.clear()
    wbi_config.update(original)


@pytest.fixture(autouse=True)
def reset_library_state():
    """Reset the module-level caches of the library between tests."""
    wbi_helpers.properties_dt.clear()
    wbi_fastrun.fastrun_store.clear()
    yield
    wbi_helpers.properties_dt.clear()
    wbi_fastrun.fastrun_store.clear()


@pytest.fixture(autouse=True)
def no_sleep(request, monkeypatch):
    """Neutralize retry/backoff wait times so error-path tests stay fast."""
    if request.node.get_closest_marker('integration'):
        # Real instances need real wait times.
        yield
        return
    monkeypatch.setattr('wikibaseintegrator.wbi_helpers.sleep', lambda seconds: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    yield


@pytest.fixture
def wikibase(requests_mock, preserve_config):
    """A simulated Wikibase instance, with wbi_config pointing to it."""
    instance = MockWikibase(requests_mock)
    wbi_config['MEDIAWIKI_API_URL'] = instance.mediawiki_api_url
    wbi_config['MEDIAWIKI_INDEX_URL'] = instance.mediawiki_index_url
    wbi_config['MEDIAWIKI_REST_URL'] = instance.mediawiki_rest_url
    wbi_config['SPARQL_ENDPOINT_URL'] = instance.sparql_endpoint_url
    wbi_config['WIKIBASE_URL'] = instance.base_url
    return instance


@pytest.fixture
def item_q582(wikibase):
    """The simulated instance populated with the reference item Q582."""
    return wikibase.add_fixture('item_Q582')
