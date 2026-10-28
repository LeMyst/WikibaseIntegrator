"""
Interaction tests for MediaInfoEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator

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
        with pytest.raises(Exception, match='Title not found'):
            wbi.mediainfo.get_by_title(titles='File:Missing.jpg')

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


class TestEntityUrl:
    def test_entity_url(self, wikibase):
        base = wikibase.base_url
        assert wbi.mediainfo.new(id='M75908279').get_entity_url() == base + '/entity/M75908279'
        assert wbi.mediainfo.new(id='75908279').get_entity_url() == base + '/entity/M75908279'
        assert wbi.mediainfo.new(id=75908279).get_entity_url() == base + '/entity/M75908279'
