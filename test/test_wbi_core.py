import unittest
from copy import deepcopy

from wikibaseintegrator import datatypes, WikibaseIntegrator
from wikibaseintegrator.datatypes import String, Math, ExternalID, Time, URL, MonolingualText, Quantity, CommonsMedia, GlobeCoordinate, GeoShape, Property, TabularData, \
    MusicalNotation, Lexeme, Form, Sense
from wikibaseintegrator.entities import Item
from wikibaseintegrator.models import LanguageValues
from wikibaseintegrator.wbi_helpers import search_entities, generate_entity_instances

wbi = WikibaseIntegrator()


class TestWbiCore(unittest.TestCase):
    common_item = wbi.item.new().get('Q2')

    def test_item_engine(self):
        Item(api=wbi)
        wbi.item.new()
        Item(api=wbi).add_claims(String(value='test', prop_nr='P1'))
        Item(api=wbi).add_claims([String(value='test', prop_nr='P1')])
        Item(api=wbi, id='Q2')
        with self.assertRaises(TypeError):
            Item(api=wbi).add_claims('test')

    def test_search_only(self):
        item = wbi.item.new().get(entity_id='Q2')

        assert item.labels.get('en').value == "Earth"

        descr = item.descriptions.get('en').value
        assert len(descr) > 3

        assert "Terra" in item.aliases.get('es')
        assert "planet" in item.descriptions.get('en')

        assert item.labels.get('es') == "Tierra"

    def test_basedatatype_if_exists(self):
        instances = [datatypes.Item(prop_nr='P31', value='Q1234'), datatypes.Item(prop_nr='P31', value='Q1234')]
        item_original = wbi.item.get('Q2')
        len_claims_original = len([x.mainsnak.datavalue['value']['id'] for x in item_original.claims.get('P31')])

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='APPEND')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, only one unique added
        assert len(claims) == len_claims_original + 1 and 'Q1234' in claims and claims.count('Q1234') == 1

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='FORCE_APPEND')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, force two to be added
        assert len(claims) == len_claims_original + 2 and 'Q1234' in claims and claims.count('Q1234') == 2

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='KEEP')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, there is already claims, so nothing added
        assert len(claims) == len_claims_original and 'Q1234' not in claims

        item = deepcopy(item_original)
        item.add_claims(instances, if_exists='REPLACE')
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31') if not x.removed]
        removed_claims = [True for x in item.claims.get('P31') if x.removed]
        # Append claims to item, replace already existing claims with new ones, only one if it's the same property number
        assert len(claims) == 1 and 'Q1234' in claims and len(removed_claims) == 2 and True in removed_claims and claims.count('Q1234') == 1

    def test_description(self):
        item = wbi.item.get('Q2')

        descr = item.descriptions.get('en').value
        assert len(descr) > 3

        assert "planet" in item.descriptions.get('en')

        # set_description on already existing description
        item.descriptions.set(value=descr)
        assert item.descriptions.get() == descr
        item.descriptions.set(value="lorem")
        assert item.descriptions.get() == "lorem"
        item.descriptions.set(language='es', value="lorem ipsum")
        assert item.descriptions.get('es') == "lorem ipsum"
        item.descriptions.set(language='en', value="lorem ipsum", if_exists='KEEP')
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem'}
        # set_description on empty desription
        item.descriptions = LanguageValues()
        item.descriptions.set(value='')
        item.descriptions.set(language='en', value="lorem ipsum", if_exists='KEEP')
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}

        item.descriptions.set(language='fr', value="lorem", if_exists='KEEP')
        item.descriptions.set(language='fr', value="lorem ipsum", if_exists='REPLACE')
        item.descriptions.set(language='en', value="lorem", if_exists='KEEP')
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}
        assert item.get_json()['descriptions']['fr'] == {'language': 'fr', 'value': 'lorem ipsum'}

        # TODO: Test deletion of description?

    def test_label(self):
        item = wbi.item.get('Q2')

        assert item.labels.get('en') == "Earth"

        assert "Terra" in item.aliases.get('es')

        assert item.labels.get("es") == "Tierra"

        item.labels.set(value='Earth')
        item.labels.set(value='xfgfdsg')
        item.labels.set(language='en', value='xfgfdsgtest', if_exists='KEEP')
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        assert item.get_json()['labels']['fr'] == {'language': 'fr', 'value': 'Terre'}
        item.aliases.set(values=["fake alias"], if_exists='APPEND')
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

        item.labels.set(language='fr', value=None)
        item.labels.set(language='non-exist-key', value=None)
        assert 'remove' in item.get_json()['labels']['fr']

        item.labels.set(language='ak')
        item.descriptions.set(language='ak')
        item.aliases.set(language='ak')
        item.labels.set(value='label', language='ak')
        item.descriptions.set(value='d', language='ak')
        item.aliases.set(values=['a'], language='ak', if_exists='APPEND')
        assert item.aliases.get('ak') == ['a']
        item.aliases.set(values='b', language='ak')
        assert item.aliases.get('ak') == ['a', 'b']
        item.aliases.set(values='b', language='ak', if_exists='REPLACE')
        assert item.aliases.get('ak') == ['b']
        item.aliases.set(values=['c'], language='ak', if_exists='REPLACE')
        assert item.aliases.get('ak') == ['c']
        item.aliases.set(values=['d'], language='ak', if_exists='KEEP')
        assert 'd' not in item.aliases.get('ak')
        item.aliases.set(language='ak', if_exists='KEEP')
        assert 'remove' not in item.get_json()['aliases']['ak'][0]
        item.aliases.set(language='ak')
        assert 'remove' in item.get_json()['aliases']['ak'][0]

    def test_wd_search(self):
        t = search_entities('rivaroxaban')
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)

    def test_entity_generator(self):
        entities = ['Q408883', 'P715', 'Q18046452']

        entity_instances = generate_entity_instances(entities=entities)

        for qid, entity in entity_instances:
            self.assertIn(qid, entities)

    def test_new_item_creation(self):
        data = [
            String(value='test1', prop_nr='P1'),
            String(value='test2', prop_nr='1'),
            String(value='test3', prop_nr=1),
            Math(value="xxx", prop_nr="P2"),
            ExternalID(value="xxx", prop_nr="P3"),
            datatypes.Item(value="Q123", prop_nr="P4"),
            datatypes.Item(value="123", prop_nr="P4"),
            datatypes.Item(value=123, prop_nr="P4"),
            Time(time='-0458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            Time(time='458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            Time(time='+2021-01-01T15:15:15Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            URL(value="http://www.wikidata.org", prop_nr="P6"),
            URL(value="https://www.wikidata.org", prop_nr="P6"),
            URL(value="ftp://example.com", prop_nr="P6"),
            URL(value="ssh://user@server/project.git", prop_nr="P6"),
            URL(value="svn+ssh://user@server:8888/path", prop_nr="P6"),
            MonolingualText(text="xxx", language="fr", prop_nr="P7"),
            Quantity(quantity=-5.04, prop_nr="P8"),
            Quantity(quantity=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P8"),
            CommonsMedia(value="xxx", prop_nr="P9"),
            GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr="P10"),
            GeoShape(value="Data:xxx.map", prop_nr="P11"),
            Property(value="P123", prop_nr="P12"),
            Property(value="123", prop_nr="P12"),
            Property(value=123, prop_nr="P12"),
            TabularData(value="Data:Taipei+Population.tab", prop_nr="P13"),
            MusicalNotation(value="\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P14"),
            Lexeme(value="L123", prop_nr="P15"),
            Lexeme(value="123", prop_nr="P15"),
            Lexeme(value=123, prop_nr="P15"),
            Form(value="L123-F123", prop_nr="P16"),
            Sense(value="L123-S123", prop_nr="P17")
        ]

        for d in data:
            item = wbi.item.new().add_claims([d])
            assert item.get_json()
            item = wbi.item.new().add_claims(d)
            assert item.get_json()

        item = wbi.item.new().add_claims(data)
        assert item.get_json()

    def test_get_property_list(self):
        self.assertTrue(len(self.common_item.claims))

    def test_count_references(self):
        self.assertTrue(len(self.common_item.claims.get('P2067')[0].references))

    def test_get_qualifier_properties(self):
        self.assertTrue(len(self.common_item.claims.get(property='P2067')))
