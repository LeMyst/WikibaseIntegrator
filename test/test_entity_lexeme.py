import unittest

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Form, Sense
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_lexeme.py)'

wbi = WikibaseIntegrator()


class TestEntityLexeme(unittest.TestCase):

    def test_get(self):
        # Test with complete id
        assert wbi.lexeme.get('L5').id == 'L5'
        # Test with numeric id as string
        assert wbi.lexeme.get('5').id == 'L5'
        # Test with numeric id as int
        assert wbi.lexeme.get(5).id == 'L5'

        # Test with invalid id
        with self.assertRaises(ValueError):
            wbi.lexeme.get('Q5')

        # Test with zero id
        with self.assertRaises(ValueError):
            wbi.lexeme.get(0)

        # Test with negative id
        with self.assertRaises(ValueError):
            wbi.lexeme.get(-1)

    def test_get_json(self):
        assert wbi.lexeme.get('L5').get_json()['forms'][0]['representations']['es']['value'] == 'pinos'

    def test_long_item_id(self):
        assert wbi.lexeme.get('Lexeme:L582').id == 'L582'

    def test_entity_url(self):
        assert wbi.lexeme.new(id='L582').get_entity_url() == 'http://www.wikidata.org/entity/L582'
        assert wbi.lexeme.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/L582'
        assert wbi.lexeme.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/L582'

    # Test if the language is correctly formatted (T338255)
    def test_wrong_language(self):
        assert wbi.lexeme.new(language='http://www.wikidata.org/entity/Q397').language == 'Q397'
        assert wbi.lexeme.new(language='wd:Q397').language == 'Q397'
        assert wbi.lexeme.new(language='Q397').language == 'Q397'
        assert wbi.lexeme.new(language='397').language == 'Q397'
        assert wbi.lexeme.new(language=397).language == 'Q397'

    def test_get_lexeme_id(self):
        assert Form(value='L123-F123', prop_nr='P16').get_lexeme_id() == 'L123'
        assert Sense(value='L123-S123', prop_nr='P16').get_lexeme_id() == 'L123'
