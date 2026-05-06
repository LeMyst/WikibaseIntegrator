import unittest
from copy import deepcopy
from unittest.mock import patch

import pytest
import requests

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import BaseDataType, Item, MonolingualText, String
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import NonExistentEntityError

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'

wbi = WikibaseIntegrator()


def _build_q582_entity(props=None):
    full_entity = {
        'id': 'Q582',
        'type': 'item',
        'lastrevid': 1,
        'labels': {
            'fr': {
                'language': 'fr',
                'value': 'Villeurbanne'
            }
        },
        'descriptions': {
            'fr': {
                'language': 'fr',
                'value': 'commune francaise'
            }
        },
        'aliases': {
            'fr': [
                {
                    'language': 'fr',
                    'value': 'Villeur'
                }
            ]
        },
        'sitelinks': {
            'frwiki': {
                'site': 'frwiki',
                'title': 'Villeurbanne',
                'badges': []
            }
        },
        'claims': {
            'P443': [
                {
                    'mainsnak': {
                        'snaktype': 'value',
                        'property': 'P443',
                        'datatype': 'string',
                        'datavalue': {
                            'value': 'audio.ogg',
                            'type': 'string'
                        }
                    },
                    'type': 'statement',
                    'id': 'Q582$P443-1',
                    'rank': 'normal',
                    'qualifiers': {
                        'P407': [
                            {
                                'snaktype': 'value',
                                'property': 'P407',
                                'datatype': 'wikibase-item',
                                'datavalue': {
                                    'value': {
                                        'entity-type': 'item',
                                        'numeric-id': 150,
                                        'id': 'Q150'
                                    },
                                    'type': 'wikibase-entityid'
                                }
                            }
                        ]
                    },
                    'qualifiers-order': ['P407']
                }
            ],
            'P2581': [
                {
                    'mainsnak': {
                        'snaktype': 'value',
                        'property': 'P2581',
                        'datatype': 'string',
                        'datavalue': {
                            'value': '98765',
                            'type': 'string'
                        }
                    },
                    'type': 'statement',
                    'id': 'Q582$P2581-1',
                    'rank': 'normal',
                    'references': [
                        {
                            'hash': 'deadbeef',
                            'snaks': {
                                'P854': [
                                    {
                                        'snaktype': 'value',
                                        'property': 'P854',
                                        'datatype': 'string',
                                        'datavalue': {
                                            'value': 'https://example.org/source',
                                            'type': 'string'
                                        }
                                    }
                                ]
                            },
                            'snaks-order': ['P854']
                        }
                    ]
                }
            ]
        }
    }

    if props:
        if isinstance(props, str):
            requested_props = {p for p in props.split('|') if p and p != 'info'}
        else:
            requested_props = set(props)
        entity = {k: full_entity[k] for k in ('id', 'type', 'lastrevid')}
        for prop in requested_props:
            if prop in full_entity:
                entity[prop] = full_entity[prop]
        return entity

    return full_entity


def _fake_get(self, entity_id, props=None, **kwargs):
    if entity_id == 'Q99999999999999':
        raise NonExistentEntityError({'code': 'no-such-entity'})
    return {'entities': {'Q582': _build_q582_entity(props=props)}}


def _fake_edit_entity(*args, **kwargs):
    raise requests.exceptions.JSONDecodeError('mocked json decode error', 'mocked', 0)


class _FakeFastRunContainer:
    def write_required(self, data, cqid=None, action_if_exists=None):
        if not data:
            return False

        for claim in data:
            if claim.mainsnak.property_number == 'P1791':
                return True
            if claim.mainsnak.property_number == 'P2581' and len(claim.references) == 0:
                return True

        return False


def _fake_get_fastrun_container(*args, **kwargs):
    return _FakeFastRunContainer()


class TestEntityItem(unittest.TestCase):

    def setUp(self):
        self.get_patcher = patch('wikibaseintegrator.entities.baseentity.BaseEntity._get', new=_fake_get)
        self.write_patcher = patch('wikibaseintegrator.entities.baseentity.edit_entity', new=_fake_edit_entity)
        self.fastrun_patcher = patch('wikibaseintegrator.entities.baseentity.wbi_fastrun.get_fastrun_container', new=_fake_get_fastrun_container)

        self.get_patcher.start()
        self.write_patcher.start()
        self.fastrun_patcher.start()

    def tearDown(self):
        self.fastrun_patcher.stop()
        self.write_patcher.stop()
        self.get_patcher.stop()

    def test_get(self):
        # Test with complete id
        assert wbi.item.get('Q582').id == 'Q582'
        # Test with numeric id as string
        assert wbi.item.get('582').id == 'Q582'
        # Test with numeric id as int
        assert wbi.item.get(582).id == 'Q582'

        # Test with invalid id
        with self.assertRaises(ValueError):
            wbi.item.get('L5')

        # Test with zero id
        with self.assertRaises(ValueError):
            wbi.item.get(0)

        # Test with negative id
        with self.assertRaises(ValueError):
            wbi.item.get(-1)

        # Test with negative id
        with self.assertRaises(NonExistentEntityError):
            wbi.item.get("Q99999999999999")

    def test_get_json(self):
        assert wbi.item.get('Q582').get_json()['labels']['fr']['value'] == 'Villeurbanne'

    def test_write(self):
        with self.assertRaises(requests.exceptions.JSONDecodeError):
            wbi.item.get('Q582').write(allow_anonymous=True)

    def test_write_not_required(self):
        assert not wbi.item.get('Q582').write_required(base_filter=[BaseDataType(prop_nr='P1791')])

    def test_write_required(self):
        item = wbi.item.get('Q582')
        item.claims.add(Item(prop_nr='P1791', value='Q42'))
        assert item.write_required([BaseDataType(prop_nr='P1791')])

    def test_write_not_required_ref(self):
        assert not wbi.item.get('Q582').write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_write_required_ref(self):
        item = wbi.item.get('Q582')
        item.claims.get('P2581')[0].references.references.pop()
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_long_item_id(self):
        assert wbi.item.get('Item:Q582').id == 'Q582'

    def test_entity_url(self):
        assert wbi.item.new(id='Q582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/Q582'

    def test_entity_qualifers_remove(self):
        item_original = wbi.item.get('Q582')

        # clear()
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear('P666')) >= 1
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear('P407')) == 0
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear()) == 0

        # remove()
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.remove(Item(prop_nr='P407', value='Q150'))) == 0

        # common
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')) >= 1
        assert len(item.claims.get('P443')[0].qualifiers) >= 1

    def test_new_lines(self):
        item = wbi.item.new()

        with pytest.raises(ValueError):
            item.claims.add(String(prop_nr=123, value="Multi\r\nline"))
        with pytest.raises(ValueError):
            item.claims.add(String(prop_nr=123, value="Multi\rline"))
        with pytest.raises(ValueError):
            item.claims.add(String(prop_nr=123, value="Multi\nline"))

        with pytest.raises(ValueError):
            item.claims.add(MonolingualText(prop_nr=123, text="Multi\r\nline"))
            item.claims.add(MonolingualText(prop_nr=123, text="Multi\rline"))
            item.claims.add(MonolingualText(prop_nr=123, text="Multi\nline"))

    def test_get_limited_props(self):
        item = wbi.item.get('Q582', props=['labels'])
        assert item.labels.get('fr').value == 'Villeurbanne'
        assert len(item.claims) == 0
        assert len(item.sitelinks) == 0
        assert len(item.aliases) == 0
        assert len(item.descriptions) == 0

        item = wbi.item.get('Q582', props=['aliases'])
        assert len(item.aliases) > 0
        assert len(item.labels) == 0
