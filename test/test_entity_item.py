import unittest
from copy import deepcopy

import pytest
import requests

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import BaseDataType, Item, MonolingualText, String
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_exceptions import NonExistentEntityError

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'

wbi = WikibaseIntegrator()


class TestEntityItem(unittest.TestCase):

    def test_get(self):
        # Test with complete id
        assert wbi.item.get('Q582').id == 'Q582'
        # Test with numeric id as string
        assert wbi.item.get('582').id == 'Q582'
        # Test with numeric id as int
        assert wbi.item.get(582).id == 'Q582'

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
        assert wbi.item.get('Q582').get_json()['labels']['fr']['value'] == 'Villeurbanne'

    def test_write(self):
        with self.assertRaises(requests.exceptions.JSONDecodeError):
            wbi.item.get('Q582').write(allow_anonymous=True, mediawiki_api_url='https://httpstat.us/200')

    def test_write_not_required(self):
        assert not wbi.item.get('Q582').write_required(base_filter=[BaseDataType(prop_nr='P1791')])

    def test_write_required(self):
        item = wbi.item.get('Q582')
        item.claims.add(Item(prop_nr='P1791', value='Q42'))
        assert item.write_required([BaseDataType(prop_nr='P1791')])

    def test_write_not_required_ref(self):
        assert not wbi.item.get('Q582').write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_write_required_ref(self):
        item = wbi.item.get('Q582')
        item.claims.get('P2581')[0].references.references.pop()
        assert item.write_required(base_filter=[BaseDataType(prop_nr='P2581')], use_refs=True)

    def test_long_item_id(self):
        assert wbi.item.get('Item:Q582').id == 'Q582'

    def test_entity_url(self):
        assert wbi.item.new(id='Q582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/Q582'

    def test_entity_qualifers_remove(self):
        item_original = wbi.item.get('Q582')

        # clear()
        item = deepcopy(item_original)
        assert len(item.claims.get('P452')[0].qualifiers.clear('P666')) >= 1
        item = deepcopy(item_original)
        assert len(item.claims.get('P452')[0].qualifiers.clear('P1013')) == 0
        item = deepcopy(item_original)
        assert len(item.claims.get('P452')[0].qualifiers.clear()) == 0

        # remove()
        item = deepcopy(item_original)
        from pprint import pprint
        pprint(item.claims.get('P452')[0].qualifiers)
        assert len(item.claims.get('P452')[0].qualifiers.remove(Item(prop_nr='P1013', value='Q112111570'))) == 0

        # common
        item = deepcopy(item_original)
        assert len(item.claims.get('P452')) >= 1
        assert len(item.claims.get('P452')[0].qualifiers) >= 1

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

    def test_entityshape_entity_validation(self):
        random_campsite = wbi.item.get('Q119156070')
        assert random_campsite.entityshape_schema_validator(entity_schema_id="E376").is_valid
        assert random_campsite.entityshape_schema_validator(entity_schema_id="376").is_valid
        assert random_campsite.entityshape_schema_validator(entity_schema_id=376).is_valid
        assert not wbi.item.get('Q582').entityshape_schema_validator(entity_schema_id="E376").is_valid

    def test_pyshex_entity_validation(self):
        # TODO find a combination of shex and entity that is valid
        # danish noun
        result = wbi.lexeme.get('L41172').pyshex_schema_validator(entity_schema_id="E34")
        assert result.valid is False
        # This error makes no sense TODO report upstream to pyshex
        assert result.reason == 'Import failure on https://www.wikidata.org/wiki/Special:EntitySchemaText/E68'
        random_campsite = wbi.item.get('Q119156070')
        result = random_campsite.pyshex_schema_validator(entity_schema_id="E376")
        assert result.valid is False
        assert result.reason == ('  Testing wd:Q119156070 against shape campsite\n'
 '    Datatype constraint (http://www.w3.org/2001/XMLSchema#string) does not '
 'match URIRef '
 '<http://commons.wikimedia.org/wiki/Special:FilePath/Grenforsen%2005.jpg>\n'
 '  Testing wd:Q119156070 against shape campsite\n'
 '    Datatype constraint (http://www.w3.org/2001/XMLSchema#string) does not '
 'match URIRef '
 '<http://commons.wikimedia.org/wiki/Special:FilePath/Grenforsen%2005.jpg>\n'
 '  Testing wd:Q119156070 against shape campsite\n'
 '       No matching triples found for predicate wdt:P31')
        assert random_campsite.pyshex_schema_validator(entity_schema_id="376").valid is False
        assert random_campsite.pyshex_schema_validator(entity_schema_id=376).valid is False
        result2 = wbi.item.get('Q582').pyshex_schema_validator(entity_schema_id="E376")
        assert not result2.valid
        assert result2.reason == ('  Testing wd:Q582 against shape campsite\n'
 '    Triples:\n'
 '      wd:Q582 wdt:P31 wd:Q1549591 .\n'
 '      wd:Q582 wdt:P31 wd:Q484170 .\n'
 '   2 triples exceeds max {1,1}\n'
 '  Testing wd:Q582 against shape campsite\n'
 '    Node: wd:Q1549591 not in value set:\n'
 '\t {"values": ["http://www.wikidata.org/entity/Q832778", "http:...\n'
 '  Testing wd:Q582 against shape campsite\n'
 '    Node: wd:Q484170 not in value set:\n'
 '\t {"values": ["http://www.wikidata.org/entity/Q832778", "http:...\n'
 '  Testing wd:Q582 against shape campsite\n'
 '    Triples:\n'
 '      wd:Q582 wdt:P31 wd:Q1549591 .\n'
 '      wd:Q582 wdt:P31 wd:Q484170 .\n'
 '   2 triples exceeds max {1,1}\n'
 '  Testing wd:Q582 against shape campsite\n'
 '       No matching triples found for predicate wdt:P31')
