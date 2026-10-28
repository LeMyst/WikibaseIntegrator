"""
Interaction tests for LexemeEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes, wbi_login
from wikibaseintegrator.models import Form, Sense

wbi = WikibaseIntegrator()


def new_form(representation='pinos', grammatical_features=None):
    form = Form(grammatical_features=grammatical_features or ['Q146786'])
    form.representations.set(language='es', value=representation)
    return form


def new_sense(gloss='pine tree'):
    sense = Sense()
    sense.glosses.set(language='en', value=gloss)
    return sense


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


class TestWriteForm:
    def test_write_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        form = new_form()
        form.claims.add(datatypes.String(prop_nr='P828', value='a claim on a form'))

        assert lexeme.write_form(form, allow_anonymous=True) == 'L5-F3'

        edit = wikibase.last_edit
        assert edit['params']['action'] == 'wbladdform'
        assert edit['params']['lexemeId'] == 'L5'
        assert edit['data']['representations']['es'] == {'language': 'es', 'value': 'pinos'}
        assert edit['data']['grammaticalFeatures'] == ['Q146786']
        assert 'P828' in edit['data']['claims']
        # 'add' is a wbeditentity marker, the wbladdform action doesn't expect it
        assert 'add' not in edit['data']
        assert 'id' not in edit['data']

        # The id assigned by the instance is reported back on the local object
        assert form.id == 'L5-F3'
        assert wikibase.entities['L5']['forms'][-1]['id'] == 'L5-F3'

    def test_write_form_requires_a_lexeme_id(self, wikibase):
        with pytest.raises(ValueError, match='Lexeme id'):
            wbi.lexeme.new().write_form(new_form(), allow_anonymous=True)

        assert wikibase.requests == []

    def test_write_form_refuses_an_existing_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        # Sending an existing Form to wbladdform would silently duplicate it
        with pytest.raises(ValueError, match='L5-F1'):
            lexeme.write_form(lexeme.forms.get('L5-F1'), allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    def test_write_forms_only_writes_the_new_ones(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.forms.add(new_form(representation='pinillo'))
        lexeme.forms.add(new_form(representation='pinito'))

        # L5-F1 and L5-F2 already exist on the instance and must be skipped
        assert lexeme.write_forms(allow_anonymous=True) == ['L5-F3', 'L5-F4']

        added = [request for request in wikibase.requests if request.get('action') == 'wbladdform']
        assert len(added) == 2
        assert [form.id for form in lexeme.forms] == ['L5-F1', 'L5-F2', 'L5-F3', 'L5-F4']

        # Calling it again is a no-op: every Form now has an id
        assert lexeme.write_forms(allow_anonymous=True) == []


class TestWriteSense:
    def test_write_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        assert lexeme.write_sense(new_sense(gloss='a pine'), allow_anonymous=True) == 'L5-S2'

        edit = wikibase.last_edit
        assert edit['params']['action'] == 'wbladdsense'
        assert edit['params']['lexemeId'] == 'L5'
        assert edit['data']['glosses']['en'] == {'language': 'en', 'value': 'a pine'}
        assert 'add' not in edit['data']
        assert 'id' not in edit['data']

    def test_write_sense_requires_a_lexeme_id(self, wikibase):
        with pytest.raises(ValueError, match='Lexeme id'):
            wbi.lexeme.new().write_sense(new_sense(), allow_anonymous=True)

        assert wikibase.requests == []

    def test_write_sense_refuses_an_existing_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        with pytest.raises(ValueError, match='L5-S1'):
            lexeme.write_sense(lexeme.senses.get('L5-S1'), allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    def test_write_senses_only_writes_the_new_ones(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.senses.add(new_sense(gloss='a pine'))

        assert lexeme.write_senses(allow_anonymous=True) == ['L5-S2']
        assert [sense.id for sense in lexeme.senses] == ['L5-S1', 'L5-S2']
        assert lexeme.write_senses(allow_anonymous=True) == []

    def test_write_sense_refuses_a_removed_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        # The 'remove' marker would be sent to wbladdsense, which doesn't expect it
        with pytest.raises(ValueError, match='removed'):
            lexeme.write_sense(new_sense().remove(), allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    def test_write_senses_skips_the_removed_ones(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.senses.add(new_sense(gloss='a removed pine').remove())
        lexeme.senses.add(new_sense(gloss='a pine'))

        assert lexeme.write_senses(allow_anonymous=True) == ['L5-S2']
        assert wikibase.last_edit['data']['glosses']['en']['value'] == 'a pine'
        assert len(wikibase.entities['L5']['senses']) == 2


class TestWriteSubEntityAuthentication:
    def test_anonymous_write_is_refused_without_a_login(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        # Default allow_anonymous is False, an explicit login is required
        with pytest.raises(ValueError, match='allow_anonymous'):
            lexeme.write_form(new_form())

        with pytest.raises(ValueError, match='allow_anonymous'):
            lexeme.write_sense(new_sense())

    def test_login_and_is_bot_are_taken_from_the_api_instance(self, wikibase, lexeme_l5):
        wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        authenticated_wbi = WikibaseIntegrator(login=login, is_bot=True)

        lexeme = authenticated_wbi.lexeme.get('L5')
        assert lexeme.write_form(new_form(), allow_anonymous=False) == 'L5-F3'

        params = wikibase.last_edit['params']
        assert params['token'] == wikibase.csrf_token
        assert 'bot' in params

    def test_login_can_be_passed_explicitly(self, wikibase, lexeme_l5):
        wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')

        lexeme = wbi.lexeme.get('L5')
        assert lexeme.write_sense(new_sense(), login=login) == 'L5-S2'
        assert wikibase.last_edit['params']['token'] == wikibase.csrf_token
