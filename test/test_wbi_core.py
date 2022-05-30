import unittest
from copy import deepcopy

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import (URL, CommonsMedia, ExternalID, Form, GeoShape, GlobeCoordinate, Lexeme, Math, MonolingualText, MusicalNotation, Property, Quantity,
                                          Sense, String, TabularData, Time)
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.models import LanguageValues
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseDatePrecision, WikibaseRank, WikibaseSnakType
from wikibaseintegrator.wbi_helpers import generate_entity_instances, search_entities

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_wbi_core.py)'

wbi = WikibaseIntegrator()


class TestWbiCore(unittest.TestCase):
    common_item = wbi.item.new().get('Q2')

    def test_item_engine(self):
        ItemEntity(api=wbi)
        wbi.item.new()
        ItemEntity(api=wbi).add_claims(String(value='test', prop_nr='P1'))
        ItemEntity(api=wbi).add_claims([String(value='test', prop_nr='P1')])
        ItemEntity(api=wbi, id='Q2')
        with self.assertRaises(TypeError):
            ItemEntity(api=wbi).add_claims('test')

    def test_get(self):
        item = wbi.item.new().get(entity_id='Q2')

        assert item.labels.get('en').value == "Earth"

        descr = item.descriptions.get('en').value
        assert len(descr) > 3

        assert "la Terre" in item.aliases.get('fr')
        assert "planet" in item.descriptions.get('en')

        assert item.labels.get('es') == "Tierra"

    def test_basedatatype_action_if_exists(self):
        instances = [datatypes.Item(prop_nr='P31', value='Q1234'), datatypes.Item(prop_nr='P31', value='Q1234')]
        item_original = wbi.item.get('Q2')
        len_claims_original = len([x.mainsnak.datavalue['value']['id'] for x in item_original.claims.get('P31')])

        item = deepcopy(item_original)
        item.add_claims(instances, action_if_exists=ActionIfExists.APPEND)
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, only one unique added
        assert len(claims) == len_claims_original + 1 and 'Q1234' in claims and claims.count('Q1234') == 1

        item = deepcopy(item_original)
        item.add_claims(instances, action_if_exists=ActionIfExists.FORCE_APPEND)
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, force two to be added
        assert len(claims) == len_claims_original + 2 and 'Q1234' in claims and claims.count('Q1234') == 2

        item = deepcopy(item_original)
        item.add_claims(instances, action_if_exists=ActionIfExists.KEEP)
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31')]
        # Append claims to item, there is already claims, so nothing added
        assert len(claims) == len_claims_original and 'Q1234' not in claims

        item = deepcopy(item_original)
        item.add_claims(instances, action_if_exists=ActionIfExists.REPLACE)
        claims = [x.mainsnak.datavalue['value']['id'] for x in item.claims.get('P31') if not x.removed]
        removed_claims = [True for x in item.claims.get('P31') if x.removed]
        # Append claims to item, replace already existing claims with new ones, only one if it's the same property number
        assert len(claims) == 1 and 'Q1234' in claims and len(removed_claims) == len_claims_original and True in removed_claims and claims.count('Q1234') == 1

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
        item.descriptions.set(language='en', value="lorem ipsum", action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem'}
        # set_description on empty description
        item.descriptions = LanguageValues()
        item.descriptions.set(value='')
        item.descriptions.set(language='en', value="lorem ipsum", action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}

        item.descriptions.set(language='fr', value="lorem", action_if_exists=ActionIfExists.KEEP)
        item.descriptions.set(language='fr', value="lorem ipsum", action_if_exists=ActionIfExists.REPLACE)
        item.descriptions.set(language='en', value="lorem", action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}
        assert item.get_json()['descriptions']['fr'] == {'language': 'fr', 'value': 'lorem ipsum'}

        # TODO: Test deletion of description?

    def test_label(self):
        item = wbi.item.get('Q2')

        assert item.labels.get('en') == "Earth"

        assert "la Terre" in item.aliases.get('fr')

        assert item.labels.get("es") == "Tierra"

        item.labels.set(value='Earth')
        item.labels.set(value='xfgfdsg')
        item.labels.set(language='en', value='xfgfdsgtest', action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        assert item.get_json()['labels']['fr'] == {'language': 'fr', 'value': 'Terre'}
        item.aliases.set(values=["fake alias"], action_if_exists=ActionIfExists.APPEND)
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

        item.labels.set(language='fr', value=None)
        item.labels.set(language='non-exist-key', value=None)
        assert 'remove' in item.get_json()['labels']['fr']

        item.labels.set(language='ak')
        item.descriptions.set(language='ak')
        item.aliases.set(language='ak')
        item.labels.set(value='label', language='ak')
        item.descriptions.set(value='d', language='ak')
        item.aliases.set(values=['a'], language='ak', action_if_exists=ActionIfExists.APPEND)
        assert 'a' in item.aliases.get('ak')
        item.aliases.set(values='b', language='ak')
        assert all(i in item.aliases.get('ak') for i in ['a', 'b']) and len(item.aliases.get('ak')) >= 2
        item.aliases.set(values='b', language='ak', action_if_exists=ActionIfExists.REPLACE)
        assert item.aliases.get('ak') == ['b']
        item.aliases.set(values=['c'], language='ak', action_if_exists=ActionIfExists.REPLACE)
        assert item.aliases.get('ak') == ['c']
        item.aliases.set(values=['d'], language='ak', action_if_exists=ActionIfExists.KEEP)
        assert 'd' not in item.aliases.get('ak')
        item.aliases.set(language='ak', action_if_exists=ActionIfExists.KEEP)
        assert 'remove' not in item.get_json()['aliases']['ak'][0]
        item.aliases.set(language='ak')
        assert 'remove' in item.get_json()['aliases']['ak'][0]

    def test_wd_search(self):
        t = search_entities('rivaroxaban')
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)

    def test_entity_generator(self):
        entities = {
            'Q408883': {
                'etype': 'item',
                'ctype': 'ItemEntity'
            }, 'P715': {
                'etype': 'property',
                'ctype': 'PropertyEntity'
            }, 'Q18046452': {
                'etype': 'item',
                'ctype': 'ItemEntity'
            }, 'L5': {
                'etype': 'lexeme',
                'ctype': 'LexemeEntity'
            }
        }

        entity_instances = generate_entity_instances(entities=list(entities.keys()))

        for qid, entity in entity_instances:
            self.assertIn(qid, entities)
            assert entity.ETYPE == entities[qid]['etype']
            assert type(entity).__name__ == entities[qid]['ctype']

        entity_instances = generate_entity_instances(entities='Q408883')

        for qid, entity in entity_instances:
            assert qid == 'Q408883'
            assert entity.ETYPE == 'item'
            assert type(entity).__name__ == 'ItemEntity'

    def test_rank(self):
        t1 = String(value='test1', prop_nr='P1', rank='preferred')
        assert t1.rank == WikibaseRank.PREFERRED

        t2 = String(value='test1', prop_nr='P1', rank=WikibaseRank.NORMAL)
        assert t2.rank == WikibaseRank.NORMAL

        t2 = String(value='test1', prop_nr='P1', rank=WikibaseRank.DEPRECATED)
        assert t2.get_json()['rank'] == WikibaseRank.DEPRECATED.value

        with self.assertRaises(ValueError):
            String(value='test1', prop_nr='P1', rank='invalid_rank')

    def test_snaktype(self):
        t1 = String(value='test1', prop_nr='P1')
        t1.mainsnak.snaktype = 'novalue'
        assert t1.mainsnak.snaktype == WikibaseSnakType.NO_VALUE

        t2 = String(value='test1', prop_nr='P1')
        t2.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        assert t2.mainsnak.snaktype == WikibaseSnakType.UNKNOWN_VALUE

        t3 = String(value='test1', prop_nr='P1')
        t3.mainsnak.snaktype = WikibaseSnakType.KNOWN_VALUE
        assert t3.mainsnak.get_json()['snaktype'] == WikibaseSnakType.KNOWN_VALUE.value

        t4 = String(value='test1', prop_nr='P1')
        with self.assertRaises(ValueError):
            t4.mainsnak.snaktype = 'invalid_value'

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
            Time(time='-0458-01-01T00:00:00Z', before=1, after=2, precision=WikibaseDatePrecision.MILLION_YEARS, timezone=4, prop_nr="P5"),
            Time(time='+458-01-01T00:00:00Z', before=1, after=2, precision=WikibaseDatePrecision.MILLION_YEARS, timezone=4, prop_nr="P5"),
            Time(time='+2021-01-01T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            Time(time='now', before=1, after=2, precision=WikibaseDatePrecision.MILLION_YEARS, timezone=4, prop_nr="P5"),
            URL(value="http://www.wikidata.org", prop_nr="P6"),
            URL(value="https://www.wikidata.org", prop_nr="P6"),
            URL(value="ftp://example.com", prop_nr="P6"),
            URL(value="ssh://user@server/project.git", prop_nr="P6"),
            URL(value="svn+ssh://user@server:8888/path", prop_nr="P6"),
            MonolingualText(text="xxx", language="fr", prop_nr="P7"),
            Quantity(amount=-5.04, prop_nr="P8"),
            Quantity(amount=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P8"),
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

    def test_new_extra_item_creation(self):
        data = [
            EDTF(value='test1', prop_nr='P1'),
            LocalMedia(value='test2', prop_nr='P2')
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
