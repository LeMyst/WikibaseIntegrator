import unittest

import pytest

from test.wikibase_test_config import MEDIAINFO_MAIN_ID
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config

wbi = WikibaseIntegrator()

pytestmark = [pytest.mark.external_network, pytest.mark.wikibase_integration, pytest.mark.requires_commons]


class TestEntityMediaInfo(unittest.TestCase):

    def setUp(self):
        self._user_agent_exists = 'USER_AGENT' in wbi_config
        self._old_user_agent = wbi_config.get('USER_AGENT')
        self._wikibase_url_exists = 'WIKIBASE_URL' in wbi_config
        self._old_wikibase_url = wbi_config.get('WIKIBASE_URL')
        self._mediawiki_api_url_exists = 'MEDIAWIKI_API_URL' in wbi_config
        self._old_mediawiki_api_url = wbi_config.get('MEDIAWIKI_API_URL')
        wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_mediainfo.py)'
        wbi_config['WIKIBASE_URL'] = 'https://commons.wikimedia.org'
        wbi_config['MEDIAWIKI_API_URL'] = 'https://commons.wikimedia.org/w/api.php'

    def tearDown(self):
        if self._user_agent_exists:
            wbi_config['USER_AGENT'] = self._old_user_agent
        else:
            wbi_config.pop('USER_AGENT', None)
        if self._wikibase_url_exists:
            wbi_config['WIKIBASE_URL'] = self._old_wikibase_url
        else:
            wbi_config.pop('WIKIBASE_URL', None)
        if self._mediawiki_api_url_exists:
            wbi_config['MEDIAWIKI_API_URL'] = self._old_mediawiki_api_url
        else:
            wbi_config.pop('MEDIAWIKI_API_URL', None)

    def test_get(self):
        mediainfo_numeric_id = int(MEDIAINFO_MAIN_ID.lstrip('M'))
        # Test with complete id
        assert wbi.mediainfo.get(MEDIAINFO_MAIN_ID).id == MEDIAINFO_MAIN_ID
        # Test with numeric id as string
        assert wbi.mediainfo.get(str(mediainfo_numeric_id)).id == MEDIAINFO_MAIN_ID
        # Test with numeric id as int
        assert wbi.mediainfo.get(mediainfo_numeric_id).id == MEDIAINFO_MAIN_ID

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
        assert wbi.mediainfo.get(MEDIAINFO_MAIN_ID).get_json()

    def test_entity_url(self):
        mediainfo_numeric_id = int(MEDIAINFO_MAIN_ID.lstrip('M'))
        expected_url = f"https://commons.wikimedia.org/entity/{MEDIAINFO_MAIN_ID}"
        assert wbi.mediainfo.new(id=MEDIAINFO_MAIN_ID).get_entity_url() == expected_url
        assert wbi.mediainfo.new(id=str(mediainfo_numeric_id)).get_entity_url() == expected_url
        assert wbi.mediainfo.new(id=mediainfo_numeric_id).get_entity_url() == expected_url

    # Test if we can read the claims/statements of the entity
    def test_entity_claims(self):
        media = wbi.mediainfo.get(MEDIAINFO_MAIN_ID)
        assert media.claims

    # Test if we can have the statements field in the json
    def test_get_statements(self):
        media = wbi.mediainfo.get(MEDIAINFO_MAIN_ID)
        assert media.get_json()['statements']
