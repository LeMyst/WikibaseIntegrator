from __future__ import annotations

from typing import Any

import pytest

from wikibaseintegrator.wbi_exceptions import NonExistentEntityError

SKIP_OFFLINE_PATCH_MODULES = {
    'test.test_wbi_helpers',
    'test.test_wbi_login',
    'test.test_wbi_backoff',
}


def _base_claim_string(prop: str, value: str, claim_id: str) -> dict[str, Any]:
    return {
        'mainsnak': {
            'snaktype': 'value',
            'property': prop,
            'datatype': 'string',
            'datavalue': {
                'value': value,
                'type': 'string',
            },
        },
        'type': 'statement',
        'id': claim_id,
        'rank': 'normal',
    }


def _base_claim_item(prop: str, value: str, claim_id: str) -> dict[str, Any]:
    numeric_id = int(value[1:])
    return {
        'mainsnak': {
            'snaktype': 'value',
            'property': prop,
            'datatype': 'wikibase-item',
            'datavalue': {
                'value': {
                    'entity-type': 'item',
                    'numeric-id': numeric_id,
                    'id': value,
                },
                'type': 'wikibase-entityid',
            },
        },
        'type': 'statement',
        'id': claim_id,
        'rank': 'normal',
    }


def _item_q2() -> dict[str, Any]:
    p2067_claim = _base_claim_string('P2067', '1.23', 'Q2$P2067-1')
    p2067_claim['references'] = [
        {
            'hash': 'q2ref',
            'snaks': {
                'P854': [
                    {
                        'snaktype': 'value',
                        'property': 'P854',
                        'datatype': 'string',
                        'datavalue': {'value': 'https://example.org/earth', 'type': 'string'},
                    }
                ]
            },
            'snaks-order': ['P854'],
        }
    ]

    return {
        'id': 'Q2',
        'type': 'item',
        'lastrevid': 1,
        'labels': {
            'en': {'language': 'en', 'value': 'Earth'},
            'es': {'language': 'es', 'value': 'Tierra'},
            'fr': {'language': 'fr', 'value': 'Terre'},
        },
        'descriptions': {
            'en': {'language': 'en', 'value': 'planet in the Solar System'},
            'fr': {'language': 'fr', 'value': 'planete du systeme solaire'},
        },
        'aliases': {
            'fr': [{'language': 'fr', 'value': 'la Terre'}],
            'en': [{'language': 'en', 'value': 'Planet Earth'}],
        },
        'sitelinks': {
            'enwiki': {'site': 'enwiki', 'title': 'Earth', 'badges': []},
        },
        'claims': {
            'P31': [_base_claim_item('P31', 'Q3504248', 'Q2$P31-1')],
            'P2067': [p2067_claim],
        },
    }


def _item_q582() -> dict[str, Any]:
    return {
        'id': 'Q582',
        'type': 'item',
        'lastrevid': 1,
        'labels': {'fr': {'language': 'fr', 'value': 'Villeurbanne'}},
        'descriptions': {'fr': {'language': 'fr', 'value': 'commune francaise'}},
        'aliases': {'fr': [{'language': 'fr', 'value': 'Villeur'}]},
        'sitelinks': {'frwiki': {'site': 'frwiki', 'title': 'Villeurbanne', 'badges': []}},
        'claims': {
            'P31': [_base_claim_item('P31', 'Q484170', 'Q582$P31-1')],
        },
    }


def _item_q622901() -> dict[str, Any]:
    return {
        'id': 'Q622901',
        'type': 'item',
        'lastrevid': 1,
        'labels': {'en': {'language': 'en', 'value': 'Sample'}},
        'descriptions': {'en': {'language': 'en', 'value': 'sample item'}},
        'aliases': {},
        'sitelinks': {'enwiki': {'site': 'enwiki', 'title': 'Sample title', 'badges': []}},
        'claims': {},
    }


def _item_q27869338() -> dict[str, Any]:
    return {
        'id': 'Q27869338',
        'type': 'item',
        'lastrevid': 1,
        'labels': {'en': {'language': 'en', 'value': 'No sitelinks'}},
        'descriptions': {'en': {'language': 'en', 'value': 'no sitelinks item'}},
        'aliases': {},
        'sitelinks': {},
        'claims': {},
    }


def _property_p50() -> dict[str, Any]:
    return {
        'id': 'P50',
        'type': 'property',
        'lastrevid': 1,
        'datatype': 'wikibase-item',
        'labels': {'fr': {'language': 'fr', 'value': 'auteur ou autrice'}},
        'descriptions': {'en': {'language': 'en', 'value': 'author'}},
        'aliases': {},
        'claims': {},
    }


def _property_p715() -> dict[str, Any]:
    return {
        'id': 'P715',
        'type': 'property',
        'lastrevid': 1,
        'datatype': 'string',
        'labels': {'en': {'language': 'en', 'value': 'Drugbank ID'}},
        'descriptions': {},
        'aliases': {},
        'claims': {},
    }


def _property_generic(entity_id: str) -> dict[str, Any]:
    return {
        'id': entity_id,
        'type': 'property',
        'lastrevid': 1,
        'datatype': 'string',
        'labels': {'en': {'language': 'en', 'value': f'Property {entity_id}'}},
        'descriptions': {},
        'aliases': {},
        'claims': {},
    }


def _lexeme(entity_id: str = 'L5') -> dict[str, Any]:
    return {
        'id': entity_id,
        'type': 'lexeme',
        'lastrevid': 1,
        'lemmas': {'es': {'language': 'es', 'value': 'pino'}},
        'lexicalCategory': 'Q1084',
        'language': 'Q1321',
        'forms': [
            {
                'id': f'{entity_id}-F1',
                'representations': {'es': {'language': 'es', 'value': 'pinos'}},
                'grammaticalFeatures': ['Q146786'],
                'claims': {},
            }
        ],
        'senses': [
            {
                'id': f'{entity_id}-S1',
                'glosses': {'es': {'language': 'es', 'value': 'arbol conifer'}},
                'claims': {},
            }
        ],
        'claims': {},
    }


def _mediainfo() -> dict[str, Any]:
    return {
        'id': 'M75908279',
        'type': 'mediainfo',
        'lastrevid': 1,
        'labels': {'en': {'language': 'en', 'value': 'Sample media'}},
        'descriptions': {'en': {'language': 'en', 'value': 'media info sample'}},
        'statements': {
            'P180': [_base_claim_item('P180', 'Q42', 'M75908279$P180-1')],
        },
    }


def _entity_payload(entity_id: str) -> dict[str, Any]:
    if entity_id == 'Q99999999999999':
        raise NonExistentEntityError({'code': 'no-such-entity'})

    if entity_id == 'Q2':
        return _item_q2()
    if entity_id == 'Q582':
        return _item_q582()
    if entity_id == 'Q622901':
        return _item_q622901()
    if entity_id == 'Q27869338':
        return _item_q27869338()
    if entity_id == 'Q408883':
        data = _item_q2().copy()
        data['id'] = 'Q408883'
        return data
    if entity_id == 'Q18046452':
        data = _item_q2().copy()
        data['id'] = 'Q18046452'
        return data
    if entity_id == 'P50':
        return _property_p50()
    if entity_id == 'P715':
        return _property_p715()
    if entity_id.startswith('P'):
        return _property_generic(entity_id)
    if entity_id == 'L5':
        return _lexeme('L5')
    if entity_id.startswith('L'):
        return _lexeme(entity_id)
    if entity_id == 'M75908279':
        return _mediainfo()

    if entity_id.startswith('Q'):
        data = _item_q2().copy()
        data['id'] = entity_id
        return data

    raise KeyError(f'Unsupported fake entity: {entity_id}')


def _filter_entity_props(entity: dict[str, Any], props: str | list | None) -> dict[str, Any]:
    if not props:
        return entity

    if isinstance(props, str):
        requested_props = {p for p in props.split('|') if p and p != 'info'}
    else:
        requested_props = set(props)

    filtered = {k: entity[k] for k in ('id', 'type', 'lastrevid') if k in entity}
    for prop in requested_props:
        if prop in entity:
            filtered[prop] = entity[prop]
    return filtered


def fake_baseentity_get(self, entity_id, login=None, allow_anonymous=True, is_bot=None, props=None, **kwargs):
    del self, login, allow_anonymous, is_bot, kwargs
    payload = _entity_payload(entity_id)
    payload = _filter_entity_props(payload, props)
    return {'entities': {entity_id: payload}}


def _datatype_map() -> dict[str, str]:
    return {
        'P1433': 'wikibase-item',
        'P1476': 'monolingualtext',
        'P2093': 'string',
        'P31': 'wikibase-item',
        'P407': 'wikibase-item',
        'P50': 'wikibase-item',
        'P953': 'url',
        'P1545': 'string',
        'P699': 'external-id',
        'P828': 'wikibase-item',
        'P2888': 'url',
        'P248': 'wikibase-item',
        'P813': 'time',
        'P352': 'external-id',
        'P705': 'external-id',
        'P646': 'external-id',
    }


def fake_mediawiki_api_call_helper(data: dict[str, Any], *args, **kwargs):
    del args, kwargs
    action = data.get('action')

    if action == 'wbsearchentities':
        return {
            'success': 1,
            'search': [
                {
                    'id': 'Q999',
                    'label': 'rivaroxaban',
                    'match': {'type': 'label', 'text': 'rivaroxaban'},
                    'description': 'medication',
                    'aliases': ['xarelto'],
                }
            ],
        }

    if action == 'wbgetentities':
        if 'sites' in data and 'titles' in data:
            return {'entities': {'M75908279': _mediainfo()}}

        ids = data.get('ids', '')
        id_list = ids.split('|') if isinstance(ids, str) else list(ids)

        if data.get('props') == 'datatype':
            dt_map = _datatype_map()
            return {'entities': {prop: {'datatype': dt_map.get(prop, 'string')} for prop in id_list}}

        return {'entities': {entity_id: _entity_payload(entity_id) for entity_id in id_list}}

    return {'success': 1}


def fake_execute_sparql_query(query: str, prefix: str | None = None, endpoint: str | None = None, user_agent: str | None = None, max_retries: int = 1000, retry_after: int = 60):
    del prefix, endpoint, user_agent, max_retries, retry_after

    if 'wikibase:label' in query and 'wdt:P22 wd:Q1339' in query:
        return {'results': {'bindings': [{'child': {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q1'}} for _ in range(2)]}}

    if 'rdfs:label' in query:
        return {'results': {'bindings': [{'item': {'value': 'http://www.wikidata.org/entity/Q2'}, 'label': {'value': 'Earth'}}]}}

    if 'schema:description' in query:
        return {'results': {'bindings': [{'item': {'value': 'http://www.wikidata.org/entity/Q2'}, 'label': {'value': 'planet in the Solar System'}}]}}

    if 'skos:altLabel' in query:
        return {'results': {'bindings': [{'item': {'value': 'http://www.wikidata.org/entity/Q2'}, 'label': {'value': 'Planet Earth'}}]}}

    if '/prop/P699' in query:
        bindings = [
            {
                'sid': {'value': 'http://www.wikidata.org/entity/statement/Q10874-S1'},
                'item': {'value': 'http://www.wikidata.org/entity/Q10874'},
                'v': {'type': 'literal', 'value': 'DOID:1432'},
            }
        ]
        if 'prov:wasDerivedFrom' in query:
            bindings = [
                {
                    'sid': {'value': 'http://www.wikidata.org/entity/statement/Q10874-S1'},
                    'item': {'value': 'http://www.wikidata.org/entity/Q10874'},
                    'v': {'type': 'literal', 'value': 'DOID:1432'},
                    'ref': {'value': 'http://www.wikidata.org/entity/reference/ref1'},
                    'pr': {'value': 'http://www.wikidata.org/entity/P248'},
                    'rval': {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q30988716'},
                },
                {
                    'sid': {'value': 'http://www.wikidata.org/entity/statement/Q10874-S1'},
                    'item': {'value': 'http://www.wikidata.org/entity/Q10874'},
                    'v': {'type': 'literal', 'value': 'DOID:1432'},
                    'ref': {'value': 'http://www.wikidata.org/entity/reference/ref1'},
                    'pr': {'value': 'http://www.wikidata.org/entity/P813'},
                    'rval': {'type': 'literal', 'datatype': 'http://www.w3.org/2001/XMLSchema#dateTime', 'value': '2017-07-05T00:00:00Z'},
                },
            ]
        return {'results': {'bindings': bindings}}

    if '/prop/P828' in query:
        return {
            'results': {
                'bindings': [
                    {
                        'sid': {'value': 'http://www.wikidata.org/entity/statement/Q10874-S2'},
                        'item': {'value': 'http://www.wikidata.org/entity/Q10874'},
                        'v': {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q18228398'},
                    }
                ]
            }
        }

    if '/prop/P2888' in query:
        return {
            'results': {
                'bindings': [
                    {
                        'sid': {'value': 'http://www.wikidata.org/entity/statement/Q10874-S3'},
                        'item': {'value': 'http://www.wikidata.org/entity/Q10874'},
                        'v': {'type': 'literal', 'value': 'https://example.org/sameas'},
                    }
                ]
            }
        }

    if '/prop/P352' in query:
        return {
            'results': {
                'bindings': [
                    {
                        'sid': {'value': 'http://www.wikidata.org/entity/statement/Q100-S1'},
                        'item': {'value': 'http://www.wikidata.org/entity/Q100'},
                        'v': {'type': 'literal', 'value': 'P40095'},
                    }
                ]
            }
        }

    if '/prop/P705' in query:
        return {
            'results': {
                'bindings': [
                    {
                        'sid': {'value': 'http://www.wikidata.org/entity/statement/Q100-S2'},
                        'item': {'value': 'http://www.wikidata.org/entity/Q100'},
                        'v': {'type': 'literal', 'value': 'YER158C'},
                    }
                ]
            }
        }

    if '/prop/P646' in query:
        return {
            'results': {
                'bindings': [
                    {
                        'sid': {'value': 'http://www.wikidata.org/entity/statement/Q2-S4'},
                        'item': {'value': 'http://www.wikidata.org/entity/Q2'},
                        'v': {'type': 'literal', 'value': '/m/02j71'},
                    }
                ]
            }
        }

    return {'results': {'bindings': []}}


def fake_get_prop_datatype(self, prop_nr: str):
    del self
    return _datatype_map().get(prop_nr, 'string')


@pytest.fixture(autouse=True)
def offline_network_mocks(monkeypatch, request):
    module_name = request.module.__name__ if request.module else ''
    if module_name in SKIP_OFFLINE_PATCH_MODULES:
        return

    monkeypatch.setattr('wikibaseintegrator.entities.baseentity.BaseEntity._get', fake_baseentity_get)
    monkeypatch.setattr('wikibaseintegrator.wbi_helpers.mediawiki_api_call_helper', fake_mediawiki_api_call_helper)
    monkeypatch.setattr('wikibaseintegrator.wbi_helpers.execute_sparql_query', fake_execute_sparql_query)
    monkeypatch.setattr('wikibaseintegrator.wbi_fastrun.execute_sparql_query', fake_execute_sparql_query)
    monkeypatch.setattr('wikibaseintegrator.wbi_fastrun.FastRunContainer.get_prop_datatype', fake_get_prop_datatype)
