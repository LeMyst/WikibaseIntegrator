"""
Interaction tests for LexemeEntity against the simulated Wikibase instance.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes, wbi_login
from wikibaseintegrator.entities.baseentity import _new_entity_data
from wikibaseintegrator.models import Form, Sense
from wikibaseintegrator.wbi_exceptions import MWApiError

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


    def test_write_as_new_adds_the_forms_and_senses(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.claims.get('P5185')[0].remove()
        lexeme.senses.get('L5-S1').remove()
        lexeme.forms.get('L5-F1').representations.set('es', None)
        lexeme.write(allow_anonymous=True, as_new=True)

        data = wikibase.last_edit['data']
        assert wikibase.last_edit['params']['new'] == 'lexeme'
        assert 'id' not in data
        assert data['claims'] == {}
        # The forms and senses are new ones: no id of L5, and the removed sense isn't sent
        assert [set(form) for form in data['forms']] == [{'representations', 'grammaticalFeatures', 'claims', 'add'}] * 2
        assert all('remove' not in representation for representation in data['forms'][0]['representations'].values())
        assert data['senses'] == []


    def test_new_entity_data_of_partial_sub_entities(self):
        # The data given to _write() by hand can have forms and senses without terms or claims
        data = {'id': 'L5', 'forms': [{'id': 'L5-F1', 'grammaticalFeatures': []}], 'senses': [{'id': 'L5-S1'}, {'id': 'L5-S2', 'remove': ''}]}
        _new_entity_data(data)
        assert data == {'forms': [{'grammaticalFeatures': [], 'add': ''}], 'senses': [{'add': ''}]}


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


    def test_write_form_refuses_a_removed_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        # The 'remove' marker would be sent to wbladdform, which doesn't expect it
        with pytest.raises(ValueError, match='removed'):
            lexeme.write_form(new_form().remove(), allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    def test_write_forms_skips_the_removed_ones(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.forms.add(new_form(representation='pinillo').remove())
        lexeme.forms.add(new_form(representation='pinito'))

        assert lexeme.write_forms(allow_anonymous=True) == ['L5-F3']
        assert wikibase.last_edit['data']['representations']['es']['value'] == 'pinito'


class TestRemoveForm:
    def test_write_sends_the_removed_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        assert lexeme.forms.get('L5-F1').remove() is lexeme.forms.get('L5-F1')
        lexeme.write(allow_anonymous=True)

        forms = {form['id']: form for form in wikibase.last_edit['data']['forms']}
        assert 'remove' in forms['L5-F1']
        assert 'remove' not in forms['L5-F2']

    def test_new_removed_form_is_left_out(self, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.forms.add(new_form().remove())
        assert [form['id'] for form in lexeme.get_json()['forms']] == ['L5-F1', 'L5-F2']


class TestEditAndRemoveForm:
    def test_edit_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        form = lexeme.forms.get('L5-F1')
        form.representations.set(language='es', value='pinares')
        form.representations.set(language='en', value='pines')
        form.grammatical_features = ['Q1084']
        form.claims.add(datatypes.String(prop_nr='P828', value='a claim on a form'))

        assert lexeme.edit_form(form, allow_anonymous=True) is form

        edit = wikibase.last_edit
        assert edit['params']['action'] == 'wbleditformelements'
        assert edit['params']['formId'] == 'L5-F1'
        assert 'id' not in edit['data']
        assert edit['data']['representations']['en'] == {'language': 'en', 'value': 'pines'}
        assert edit['data']['grammaticalFeatures'] == ['Q1084']

        stored = wikibase.entities['L5']['forms']
        assert stored[0]['representations'] == {'es': {'language': 'es', 'value': 'pinares'}, 'en': {'language': 'en', 'value': 'pines'}}
        assert stored[0]['grammaticalFeatures'] == ['Q1084']
        # Only the Form is sent: the other Form is left untouched
        assert stored[1]['representations'] == {'es': {'language': 'es', 'value': 'pino'}}

        # The Form is updated from the response: its new claim has the GUID assigned by the instance
        assert form.claims.get('P828')[0].id
        assert lexeme.lastrevid == wikibase.entities['L5']['lastrevid']

    def test_edit_form_removes_what_is_marked_for_removal(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        form = lexeme.forms.get('L5-F1')
        form.representations.set(language='en', value='pines')
        form.claims.add(datatypes.String(prop_nr='P828', value='a claim on a form'))
        lexeme.edit_form(form, allow_anonymous=True)

        form.representations.set(language='en', value=None)
        form.claims.get('P828')[0].remove()
        lexeme.edit_form(form, allow_anonymous=True)

        stored = wikibase.entities['L5']['forms'][0]
        assert stored['representations'] == {'es': {'language': 'es', 'value': 'pinos'}}
        assert stored['claims'] == {}
        assert len(form.claims) == 0

    @pytest.mark.parametrize('form, error', [
        (new_form(), "has no id"),
        (Form(form_id='L6-F1'), "isn't the id of a Form of the Lexeme L5"),
        (Form(form_id='L5-S1'), "isn't the id of a Form of the Lexeme L5"),
        (Form(form_id='L5-F1').remove(), 'remove it with remove_form'),
    ], ids=['new', 'other-lexeme', 'sense-id', 'removed'])
    def test_edit_form_refuses(self, wikibase, lexeme_l5, form, error):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        with pytest.raises(ValueError, match=error):
            lexeme.edit_form(form, allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    def test_edit_form_requires_a_lexeme_id(self, wikibase):
        with pytest.raises(ValueError, match='Lexeme id'):
            wbi.lexeme.new().edit_form(Form(form_id='L5-F1'), allow_anonymous=True)

        assert wikibase.requests == []

    def test_edit_an_unknown_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        form = new_form()
        form.id = 'L5-F9'

        with pytest.raises(MWApiError, match='L5-F9'):
            lexeme.edit_form(form, allow_anonymous=True)

    @pytest.mark.parametrize('form', ['L5-F1', 'https://wikibase.example.org/entity/L5-F1', 'form object'])
    def test_remove_form(self, wikibase, lexeme_l5, form):
        lexeme = wbi.lexeme.get('L5')
        if form == 'form object':
            form = lexeme.forms.get('L5-F1')

        assert lexeme.remove_form(form, allow_anonymous=True) is None

        assert wikibase.last_edit['params']['action'] == 'wblremoveform'
        assert wikibase.last_edit['params']['id'] == 'L5-F1'
        assert [stored['id'] for stored in wikibase.entities['L5']['forms']] == ['L5-F2']
        # The Form is removed from the object too, a later write() doesn't send it again
        assert [form.id for form in lexeme.forms] == ['L5-F2']
        assert lexeme.lastrevid == wikibase.entities['L5']['lastrevid']

    def test_remove_form_refuses_another_type(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(TypeError, match='must be a Form or a Form id'):
            lexeme.remove_form(1, allow_anonymous=True)

    def test_remove_form_refuses_a_new_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(ValueError, match='add it with write_form'):
            lexeme.remove_form(new_form(), allow_anonymous=True)

    def test_write_form_hints_at_edit_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(ValueError, match=r'edit it with edit_form\(\)'):
            lexeme.write_form(lexeme.forms.get('L5-F1'), allow_anonymous=True)

    def test_unknown_lexeme_of_a_form(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.id = 'L6'

        with pytest.raises(MWApiError, match='L6-F1'):
            lexeme.remove_form('L6-F1', allow_anonymous=True)

    def test_response_without_a_revision(self, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lastrevid = lexeme.lastrevid

        lexeme._set_lastrevid({'success': 1})

        assert lexeme.lastrevid == lastrevid

    def test_write_form_updates_the_last_revision(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        lexeme.write_form(new_form(), allow_anonymous=True)

        assert lexeme.lastrevid == wikibase.entities['L5']['lastrevid']


class TestEditAndRemoveSense:
    def test_edit_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        sense = lexeme.senses.get('L5-S1')
        sense.glosses.set(language='en', value='a pine')
        sense.glosses.set(language='es', value=None)
        sense.claims.add(datatypes.String(prop_nr='P828', value='a claim on a sense'))

        assert lexeme.edit_sense(sense, allow_anonymous=True) is sense

        edit = wikibase.last_edit
        assert edit['params']['action'] == 'wbleditsenseelements'
        assert edit['params']['senseId'] == 'L5-S1'
        assert 'id' not in edit['data']

        stored = wikibase.entities['L5']['senses'][0]
        assert stored['glosses'] == {'en': {'language': 'en', 'value': 'a pine'}}
        assert 'P828' in stored['claims']
        assert lexeme.lastrevid == wikibase.entities['L5']['lastrevid']

        # The response has no claims: they are read from the lexeme, the new claim has the GUID assigned by the instance
        assert wikibase.last_request['action'] == 'wbgetentities'
        assert sense.claims.get('P828')[0].id == stored['claims']['P828'][0]['id']
        assert sense.glosses.get('en').value == 'a pine'

        # Removing the claim drops it from the Sense
        sense.claims.get('P828')[0].remove()
        lexeme.edit_sense(sense, allow_anonymous=True)
        assert wikibase.entities['L5']['senses'][0]['claims'] == {}
        assert len(sense.claims) == 0

    def test_edit_sense_with_the_claims_in_the_response(self, wikibase, lexeme_l5, monkeypatch):
        # If a version of WikibaseLexeme answers with the claims of the Sense, like wbleditformelements, the lexeme isn't read
        lexeme = wbi.lexeme.get('L5')
        sense = lexeme.senses.get('L5-S1')
        response = {'sense': {'id': 'L5-S1', 'glosses': {'en': {'language': 'en', 'value': 'a pine'}}, 'claims': {}}, 'lastrevid': 42, 'success': 1}
        monkeypatch.setattr('wikibaseintegrator.entities.lexeme.lexeme_edit_sense', lambda **kwargs: response)
        requests_before = len(wikibase.requests)

        assert lexeme.edit_sense(sense, allow_anonymous=True).glosses.get('en').value == 'a pine'
        assert len(wikibase.requests) == requests_before
        assert lexeme.lastrevid == 42

    @pytest.mark.parametrize('sense, error', [
        (new_sense(), "has no id"),
        (Sense(sense_id='L6-S1'), "isn't the id of a Sense of the Lexeme L5"),
        (Sense(sense_id='L5-S1').remove(), 'remove it with remove_sense'),
    ], ids=['new', 'other-lexeme', 'removed'])
    def test_edit_sense_refuses(self, wikibase, lexeme_l5, sense, error):
        lexeme = wbi.lexeme.get('L5')
        requests_before = len(wikibase.requests)

        with pytest.raises(ValueError, match=error):
            lexeme.edit_sense(sense, allow_anonymous=True)

        assert len(wikibase.requests) == requests_before

    @pytest.mark.parametrize('sense', ['L5-S1', 'sense object'])
    def test_remove_sense(self, wikibase, lexeme_l5, sense):
        lexeme = wbi.lexeme.get('L5')
        if sense == 'sense object':
            sense = lexeme.senses.get('L5-S1')

        assert lexeme.remove_sense(sense, allow_anonymous=True) is None

        assert wikibase.last_edit['params']['action'] == 'wblremovesense'
        assert wikibase.last_edit['params']['id'] == 'L5-S1'
        assert wikibase.entities['L5']['senses'] == []
        assert len(lexeme.senses) == 0
        assert lexeme.lastrevid == wikibase.entities['L5']['lastrevid']

    def test_remove_an_unknown_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(MWApiError, match='L5-S9'):
            lexeme.remove_sense('L5-S9', allow_anonymous=True)

        assert [sense.id for sense in lexeme.senses] == ['L5-S1']

    def test_write_sense_hints_at_edit_sense(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(ValueError, match=r'edit it with edit_sense\(\)'):
            lexeme.write_sense(lexeme.senses.get('L5-S1'), allow_anonymous=True)


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

    @pytest.mark.parametrize('method, argument', [('edit_form', 'L5-F1'), ('remove_form', 'L5-F1'), ('edit_sense', 'L5-S1'), ('remove_sense', 'L5-S1')])
    def test_edit_and_remove_take_the_login_of_the_api_instance(self, wikibase, lexeme_l5, method, argument):
        wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')
        lexeme = WikibaseIntegrator(login=login, is_bot=True).lexeme.get('L5')
        sub_entity = lexeme.forms.get(argument) if 'form' in method else lexeme.senses.get(argument)

        getattr(lexeme, method)(sub_entity)

        params = wikibase.last_edit['params']
        assert params['token'] == wikibase.csrf_token
        assert 'bot' in params

    def test_edit_and_remove_refuse_an_anonymous_edit(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        with pytest.raises(ValueError, match='allow_anonymous'):
            lexeme.edit_form(lexeme.forms.get('L5-F1'))

        with pytest.raises(ValueError, match='allow_anonymous'):
            lexeme.remove_sense('L5-S1')

    def test_login_can_be_passed_explicitly(self, wikibase, lexeme_l5):
        wikibase.valid_credentials['TestUser@bot'] = 'botpassword'
        login = wbi_login.Login(user='TestUser@bot', password='botpassword')

        lexeme = wbi.lexeme.get('L5')
        assert lexeme.write_sense(new_sense(), login=login) == 'L5-S2'
        assert wikibase.last_edit['params']['token'] == wikibase.csrf_token
