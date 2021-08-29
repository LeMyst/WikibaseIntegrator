import unittest
from pprint import pprint

from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()


class TestEntityProperty(unittest.TestCase):

    def test_get(self):
        # Test with complete id
        assert wbi.property.get('P50').id == 'P50'
        # Test with numeric id as string
        assert wbi.property.get('50').id == 'P50'
        # Test with numeric id as int
        assert wbi.property.get(50).id == 'P50'

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
        assert wbi.property.get('P50', mediawiki_api_url='https://commons.wikimedia.org/w/api.php').get_json()['labels']['fr']['value'] == 'auteur'
