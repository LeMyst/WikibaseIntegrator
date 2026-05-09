import unittest
from test.wikibase_test_config import LEXEME_MAIN_ID, configure_endpoints_from_env

import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.models import Form
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_lexeme.py)'
configure_endpoints_from_env()

pytestmark = [pytest.mark.external_network, pytest.mark.wikibase_integration]

wbi = WikibaseIntegrator()


class TestEntityLexeme(unittest.TestCase):

    def test_get(self):
        lexeme_numeric_id = int(LEXEME_MAIN_ID.lstrip('L'))
        # Test with complete id
        assert wbi.lexeme.get(LEXEME_MAIN_ID).id == LEXEME_MAIN_ID
        # Test with numeric id as string
        assert wbi.lexeme.get(str(lexeme_numeric_id)).id == LEXEME_MAIN_ID
        # Test with numeric id as int
        assert wbi.lexeme.get(lexeme_numeric_id).id == LEXEME_MAIN_ID

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
        assert wbi.lexeme.get(LEXEME_MAIN_ID).get_json()['forms'][0]['representations']['es']['value']

    def test_long_item_id(self):
        assert wbi.lexeme.get(f'Lexeme:{LEXEME_MAIN_ID}').id == LEXEME_MAIN_ID

    def test_entity_url(self):
        lexeme_numeric_id = int(LEXEME_MAIN_ID.lstrip('L'))
        expected_url = f"{wbi_config['WIKIBASE_URL']}/entity/{LEXEME_MAIN_ID}"
        assert wbi.lexeme.new(id=LEXEME_MAIN_ID).get_entity_url() == expected_url
        assert wbi.lexeme.new(id=str(lexeme_numeric_id)).get_entity_url() == expected_url
        assert wbi.lexeme.new(id=lexeme_numeric_id).get_entity_url() == expected_url

    # Test if the language is correctly formatted (T338255)
    def test_wrong_language(self):
        assert wbi.lexeme.new(language='http://www.wikidata.org/entity/Q397').language == 'Q397'
        assert wbi.lexeme.new(language='wd:Q397').language == 'Q397'
        assert wbi.lexeme.new(language='Q397').language == 'Q397'
        assert wbi.lexeme.new(language='397').language == 'Q397'
        assert wbi.lexeme.new(language=397).language == 'Q397'

    def test_get_lexeme_id(self):
        assert datatypes.Form(value='L123-F123', prop_nr='P16').get_lexeme_id() == 'L123'
        assert datatypes.Sense(value='L123-S123', prop_nr='P16').get_lexeme_id() == 'L123'

    def test_get_forms(self):
        lexeme = wbi.lexeme.new()

        form = Form(form_id=f'{LEXEME_MAIN_ID}-F4')
        form.representations.set(language='en', value='English form representation')
        form.representations.set(language='fr', value='French form representation')
        claim = datatypes.String(prop_nr='P828', value="Create a string claim for form")
        form.claims.add(claim)
        lexeme.forms.add(form)

        form = Form(form_id=f'{LEXEME_MAIN_ID}-F5')
        form.representations.set(language='en', value='English form representation')
        form.representations.set(language='fr', value='French form representation')
        claim = datatypes.String(prop_nr='P828', value="Create a string claim for form")
        form.claims.add(claim)
        lexeme.forms.add(form)

        form = Form()
        form.representations.set(language='en', value='English form representation')
        form.representations.set(language='fr', value='French form representation')
        claim = datatypes.String(prop_nr='P828', value="Create a string claim for form")
        form.claims.add(claim)
        lexeme.forms.add(form)

        form = Form()
        form.representations.set(language='en', value='English form representation')
        form.representations.set(language='fr', value='French form representation')
        claim = datatypes.String(prop_nr='P828', value="Create a string claim for form")
        form.claims.add(claim)
        lexeme.forms.add(form)

        assert not lexeme.forms.get(f'{LEXEME_MAIN_ID}-F3')
        assert lexeme.forms.get(f'{LEXEME_MAIN_ID}-F4') and lexeme.forms.get(f'{LEXEME_MAIN_ID}-F5')
        assert len(lexeme.forms) == 4
