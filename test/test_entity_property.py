"""
Interaction tests for PropertyEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()


@pytest.fixture
def property_p50(wikibase):
    return wikibase.add_fixture('property_P50')


class TestGet:
    def test_get_id_formats(self, property_p50):
        assert wbi.property.get('P50').id == 'P50'
        assert wbi.property.get('50').id == 'P50'
        assert wbi.property.get(50).id == 'P50'
        assert wbi.property.get('Property:P50').id == 'P50'

    def test_get_invalid_ids(self, wikibase):
        with pytest.raises(ValueError):
            wbi.property.get('L5')

        with pytest.raises(ValueError):
            wbi.property.get(0)

        with pytest.raises(ValueError):
            wbi.property.get(-1)

    def test_get_json(self, property_p50):
        assert wbi.property.get('P50').get_json()['labels']['fr']['value'] == 'auteur ou autrice'

    def test_datatype(self, property_p50):
        assert wbi.property.get('P50').datatype.value == 'wikibase-item'


class TestNew:
    def test_create_property(self):
        assert wbi.property.new(datatype='wikibase-item')

    def test_entity_url(self):
        assert wbi.property.new(id='P582').get_entity_url() == 'http://www.wikidata.org/entity/P582'
        assert wbi.property.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/P582'
        assert wbi.property.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/P582'


class TestWrite:
    def test_write_new_property(self, wikibase):
        prop = wbi.property.new(datatype='string')
        prop.labels.set(language='en', value='a test property')
        written = prop.write(allow_anonymous=True)

        edit = wikibase.last_edit
        assert edit['params']['new'] == 'property'
        assert edit['data']['datatype'] == 'string'
        assert written.id.startswith('P')
