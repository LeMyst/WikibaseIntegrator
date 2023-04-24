import unittest

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_mediainfo.py)'

wbi = WikibaseIntegrator()


class TestEntityMediaInfo(unittest.TestCase):

    def test_get(self):
        # Test with complete id
        assert wbi.mediainfo.get('M75908279', mediawiki_api_url='https://commons.wikimedia.org/w/api.php').id == 'M75908279'
        # Test with numeric id as string
        assert wbi.mediainfo.get('75908279', mediawiki_api_url='https://commons.wikimedia.org/w/api.php').id == 'M75908279'
        # Test with numeric id as int
        assert wbi.mediainfo.get(75908279, mediawiki_api_url='https://commons.wikimedia.org/w/api.php').id == 'M75908279'

        # Test with invalid id
        with self.assertRaises(ValueError):
            wbi.mediainfo.get('L5')

        # Test with zero id
        with self.assertRaises(ValueError):
            wbi.mediainfo.get(0)

        # Test with negative id
        with self.assertRaises(ValueError):
            wbi.mediainfo.get(-1)

    def test_get_json(self):
        assert wbi.mediainfo.get('M75908279', mediawiki_api_url='https://commons.wikimedia.org/w/api.php').get_json()

    def test_entity_url(self):
        assert wbi.mediainfo.new(id='M582').get_entity_url() == 'http://www.wikidata.org/entity/M582'
        assert wbi.mediainfo.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/M582'
        assert wbi.mediainfo.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/M582'
