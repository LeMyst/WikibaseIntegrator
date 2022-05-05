import unittest

import requests

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import BaseDataType, Item
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import NonExistentEntityError

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'

wbi = WikibaseIntegrator()


class TestEntityItem(unittest.TestCase):

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
            wbi.item.get('Q582').write(allow_anonymous=True, mediawiki_api_url='https://httpstat.us/200')

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
