"""
Interaction tests for MediaInfoEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import String
from wikibaseintegrator.wbi_enums import EntityField
from wikibaseintegrator.wbi_exceptions import MissingEntityException

wbi = WikibaseIntegrator()


@pytest.fixture
def mediainfo_budapest(wikibase):
    return wikibase.add_fixture('mediainfo_M75908279')


class TestGet:
    def test_get_id_formats(self, mediainfo_budapest):
        assert wbi.mediainfo.get('M75908279').id == 'M75908279'
        assert wbi.mediainfo.get('75908279').id == 'M75908279'
        assert wbi.mediainfo.get(75908279).id == 'M75908279'

    def test_get_invalid_ids(self, wikibase):
        with pytest.raises(ValueError):
            wbi.mediainfo.get('L5')

        with pytest.raises(ValueError):
            wbi.mediainfo.get(0)

        with pytest.raises(ValueError):
            wbi.mediainfo.get(-1)

    def test_get_by_title(self, wikibase, mediainfo_budapest):
        mediainfo = wbi.mediainfo.get_by_title(titles='File:2018-07-05-budapest-buda-hill.jpg')
        assert mediainfo.id == 'M75908279'

        request = wikibase.last_request
        assert request['action'] == 'wbgetentities'
        assert request['titles'] == 'File:2018-07-05-budapest-buda-hill.jpg'
        assert request['sites'] == 'commonswiki'

    def test_get_by_title_not_found(self, wikibase):
        # The API answers {'-1': {'title': 'File:Missing.jpg', 'missing': ''}}, as Wikimedia Commons does
        with pytest.raises(MissingEntityException, match='Title not found: File:Missing.jpg'):
            wbi.mediainfo.get_by_title(titles='File:Missing.jpg')

    def test_get_by_title_one_title_missing(self, wikibase, mediainfo_budapest):
        with pytest.raises(MissingEntityException, match='Title not found: File:Missing.jpg'):
            wbi.mediainfo.get_by_title(titles=['File:2018-07-05-budapest-buda-hill.jpg', 'File:Missing.jpg'])

    def test_get_by_title_uses_the_login(self, wikibase, mediainfo_budapest):
        # The request used to be anonymous whatever the login of the WikibaseIntegrator instance
        wikibase.valid_credentials['BotUser@pytest'] = 'botpassword'
        login = wbi_login.Login(user='BotUser@pytest', password='botpassword', mediawiki_api_url=wikibase.mediawiki_api_url)

        mediainfo = WikibaseIntegrator(login=login, is_bot=True).mediainfo.get_by_title(titles='File:2018-07-05-budapest-buda-hill.jpg', allow_anonymous=False)

        assert mediainfo.id == 'M75908279'
        # A request that isn't anonymous asserts the login and the bot flag of the WikibaseIntegrator instance
        assert wikibase.last_request['assert'] == 'bot'

    def test_get_by_title_allow_anonymous(self, wikibase, mediainfo_budapest):
        # allow_anonymous was forced to True: passing it raised a TypeError (multiple values for the keyword argument)
        with pytest.raises(ValueError, match="allow_anonymous can't be False and login is None"):
            wbi.mediainfo.get_by_title(titles='File:2018-07-05-budapest-buda-hill.jpg', allow_anonymous=False)

    def test_get_json_uses_statements_key(self, mediainfo_budapest):
        media_json = wbi.mediainfo.get('M75908279').get_json()
        assert media_json['statements']
        assert 'claims' not in media_json

    def test_entity_claims(self, mediainfo_budapest):
        import re

        media = wbi.mediainfo.get('M75908279')
        assert media.claims
        # The exact depicted entity may change upstream: only assert the structure.
        depicts = media.claims.get('P180')[0].mainsnak.datavalue
        assert depicts['type'] == 'wikibase-entityid'
        assert re.fullmatch(r'Q[0-9]+', depicts['value']['id'])


class TestWrite:
    # MediaInfo names the claims 'statements': limit_claims and fields_to_update used to only look at 'claims'

    def test_write_limited_claims(self, wikibase, mediainfo_budapest):
        media = wbi.mediainfo.get('M75908279')
        media.claims.add(String(prop_nr='P1259', value='test'))

        media.write(allow_anonymous=True, limit_claims=['P180'])

        assert list(wikibase.last_edit['data']['statements'].keys()) == ['P180']

    def test_write_fields_to_update_without_claims(self, wikibase, mediainfo_budapest):
        media = wbi.mediainfo.get('M75908279')

        media.write(allow_anonymous=True, fields_to_update=EntityField.LABELS)

        payload = wikibase.last_edit['data']
        assert 'labels' in payload
        assert 'statements' not in payload and 'descriptions' not in payload

    def test_write_fields_to_update_claims(self, wikibase, mediainfo_budapest):
        media = wbi.mediainfo.get('M75908279')

        media.write(allow_anonymous=True, fields_to_update=[EntityField.CLAIMS])

        payload = wikibase.last_edit['data']
        assert 'P180' in payload['statements']
        assert 'labels' not in payload and 'descriptions' not in payload


class TestEntityUrl:
    def test_entity_url(self, wikibase):
        base = wikibase.base_url
        assert wbi.mediainfo.new(id='M75908279').get_entity_url() == base + '/entity/M75908279'
        assert wbi.mediainfo.new(id='75908279').get_entity_url() == base + '/entity/M75908279'
        assert wbi.mediainfo.new(id=75908279).get_entity_url() == base + '/entity/M75908279'
