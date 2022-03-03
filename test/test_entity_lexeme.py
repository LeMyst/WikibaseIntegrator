import unittest

from wikibaseintegrator import WikibaseIntegrator
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
