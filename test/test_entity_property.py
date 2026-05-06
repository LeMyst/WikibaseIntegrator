import unittest

import pytest

from test.wikibase_test_config import PROPERTY_AUTHOR_ID, configure_endpoints_from_env
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_property.py)'
configure_endpoints_from_env()

pytestmark = [pytest.mark.external_network, pytest.mark.wikibase_integration]

wbi = WikibaseIntegrator()


class TestEntityProperty(unittest.TestCase):

    def test_get(self):
        property_numeric_id = int(PROPERTY_AUTHOR_ID.lstrip('P'))
        # Test with complete id
        assert wbi.property.get(PROPERTY_AUTHOR_ID).id == PROPERTY_AUTHOR_ID
        # Test with numeric id as string
        assert wbi.property.get(str(property_numeric_id)).id == PROPERTY_AUTHOR_ID
        # Test with numeric id as int
        assert wbi.property.get(property_numeric_id).id == PROPERTY_AUTHOR_ID

        # Test with invalid id
        with self.assertRaises(ValueError):
            wbi.property.get('L5')

        # Test with zero id
        with self.assertRaises(ValueError):
            wbi.property.get(0)

        # Test with negative id
        with self.assertRaises(ValueError):
            wbi.property.get(-1)

    def test_get_json(self):
        assert wbi.property.get(PROPERTY_AUTHOR_ID).get_json()['labels']['fr']['value']

    def test_create_property(self):
        wbi.property.new(datatype='wikibase-item')

    def test_long_item_id(self):
        assert wbi.property.get(f'Property:{PROPERTY_AUTHOR_ID}').id == PROPERTY_AUTHOR_ID

    def test_entity_url(self):
        property_numeric_id = int(PROPERTY_AUTHOR_ID.lstrip('P'))
        expected_url = f"{wbi_config['WIKIBASE_URL']}/entity/{PROPERTY_AUTHOR_ID}"
        assert wbi.property.new(id=PROPERTY_AUTHOR_ID).get_entity_url() == expected_url
        assert wbi.property.new(id=str(property_numeric_id)).get_entity_url() == expected_url
        assert wbi.property.new(id=property_numeric_id).get_entity_url() == expected_url
