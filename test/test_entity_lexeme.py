"""
Interaction tests for LexemeEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()


@pytest.fixture
def lexeme_l5(wikibase):
    return wikibase.add_fixture('lexeme_L5')


class TestGet:
    def test_get_id_formats(self, lexeme_l5):
        assert wbi.lexeme.get('L5').id == 'L5'
        assert wbi.lexeme.get('5').id == 'L5'
        assert wbi.lexeme.get(5).id == 'L5'
        assert wbi.lexeme.get('Lexeme:L5').id == 'L5'

    def test_get_invalid_ids(self, wikibase):
        with pytest.raises(ValueError):
            wbi.lexeme.get('Q5')

        with pytest.raises(ValueError):
            wbi.lexeme.get(0)

        with pytest.raises(ValueError):
            wbi.lexeme.get(-1)

    def test_get_json(self, lexeme_l5):
        lexeme_json = wbi.lexeme.get('L5').get_json()
        es_representations = {form['representations']['es']['value'] for form in lexeme_json['forms']}
        assert {'pino', 'pinos'} <= es_representations
        assert lexeme_json['lemmas']['es']['value'] == 'pino'
        assert lexeme_json['language'] == 'Q1321'

    def test_forms_and_senses(self, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        assert lexeme.forms.get('L5-F1') is not None
        es_representations = {form.representations.get('es').value for form in lexeme.forms.forms}
        assert {'pino', 'pinos'} <= es_representations
        assert lexeme.senses.get('L5-S1').glosses.get('en').value == 'pine tree'


class TestNew:
    def test_entity_url(self):
        assert wbi.lexeme.new(id='L582').get_entity_url() == 'http://www.wikidata.org/entity/L582'
        assert wbi.lexeme.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/L582'
        assert wbi.lexeme.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/L582'

    # Test if the language is correctly formatted (T338255)
    def test_language_normalization(self):
        assert wbi.lexeme.new(language='http://www.wikidata.org/entity/Q397').language == 'Q397'
        assert wbi.lexeme.new(language='wd:Q397').language == 'Q397'
        assert wbi.lexeme.new(language='Q397').language == 'Q397'
        assert wbi.lexeme.new(language='397').language == 'Q397'
        assert wbi.lexeme.new(language=397).language == 'Q397'


class TestWrite:
    def test_write_roundtrip(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.lemmas.set(language='es', value='pino')
        written = lexeme.write(allow_anonymous=True)

        edit = wikibase.last_edit
        assert edit['params']['id'] == 'L5'
        assert edit['data']['lemmas']['es'] == {'language': 'es', 'value': 'pino'}
        assert edit['data']['lexicalCategory'] == 'Q1084'
        assert written.id == 'L5'
        assert written.lemmas.get('es') == 'pino'
