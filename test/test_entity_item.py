import os
import unittest
from copy import deepcopy

import pytest
import requests

from test.wikibase_test_config import ITEM_CITY_ID, configure_endpoints_from_env
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import BaseDataType, Item, MonolingualText, String
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import NonExistentEntityError

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'
configure_endpoints_from_env()

pytestmark = [pytest.mark.external_network, pytest.mark.wikibase_integration]

wbi = WikibaseIntegrator()


class TestEntityItem(unittest.TestCase):

    def test_get(self):
        item_numeric_id = int(ITEM_CITY_ID.lstrip('Q'))
        # Test with complete id
        assert wbi.item.get(ITEM_CITY_ID).id == ITEM_CITY_ID
        # Test with numeric id as string
        assert wbi.item.get(str(item_numeric_id)).id == ITEM_CITY_ID
        # Test with numeric id as int
        assert wbi.item.get(item_numeric_id).id == ITEM_CITY_ID

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
        assert wbi.item.get(ITEM_CITY_ID).get_json()['labels']['fr']['value']

    def test_write(self):
        with self.assertRaises(requests.exceptions.JSONDecodeError):
            wbi.item.get(ITEM_CITY_ID).write(allow_anonymous=True, mediawiki_api_url=os.getenv("HTTPSTATUS_SERVICE", "https://httpbin.org") + "/status/200")

    def test_write_not_required(self):
        assert not wbi.item.get(ITEM_CITY_ID).write_required(base_filter=[BaseDataType(prop_nr='P1791')])

    def test_write_required(self):
        item = wbi.item.get(ITEM_CITY_ID)
        item.claims.add(Item(prop_nr='P1791', value='Q42'))
        assert item.write_required([BaseDataType(prop_nr='P1791')])

    def test_write_not_required_ref(self):
        assert not wbi.item.get(ITEM_CITY_ID).write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_write_required_ref(self):
        item = wbi.item.get(ITEM_CITY_ID)
        item.claims.get('P2581')[0].references.references.pop()
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_long_item_id(self):
        assert wbi.item.get(f'Item:{ITEM_CITY_ID}').id == ITEM_CITY_ID

    def test_entity_url(self):
        item_numeric_id = int(ITEM_CITY_ID.lstrip('Q'))
        expected_url = f"{wbi_config['WIKIBASE_URL']}/entity/{ITEM_CITY_ID}"
        assert wbi.item.new(id=ITEM_CITY_ID).get_entity_url() == expected_url
        assert wbi.item.new(id=str(item_numeric_id)).get_entity_url() == expected_url
        assert wbi.item.new(id=item_numeric_id).get_entity_url() == expected_url

    def test_entity_qualifers_remove(self):
        item_original = wbi.item.get(ITEM_CITY_ID)

        # clear()
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear('P666')) >= 1
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear('P407')) == 0
        item = deepcopy(item_original)
        assert len(item.claims.get('P443')[0].qualifiers.clear()) == 0

        # remove()
        item = deepcopy(item_original)
        from pprint import pprint
        pprint(item.claims.get('P443')[0].qualifiers)
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
        item = wbi.item.get(ITEM_CITY_ID, props=['labels'])
        assert item.labels.get('fr').value
        assert len(item.claims) == 0
        assert len(item.sitelinks) == 0
        assert len(item.aliases) == 0
        assert len(item.descriptions) == 0

        item = wbi.item.get(ITEM_CITY_ID, props=['aliases'])
        assert len(item.aliases) > 0
        assert len(item.labels) == 0
