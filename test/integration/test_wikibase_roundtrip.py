"""
End-to-end tests against a real Wikibase instance: they validate that the
library speaks the actual API correctly (entity creation, edition, search,
deletion), which the offline unit tests can only simulate.

The tests create their own properties and items, so they can run against any
empty or non-empty instance you are allowed to write to. Never point them at
a production instance.
"""
import uuid

import pytest

from wikibaseintegrator.datatypes import String
from wikibaseintegrator.models import Form, Sense
from wikibaseintegrator.wbi_exceptions import MissingEntityException
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper, search_entities

pytestmark = pytest.mark.integration

# A unique run identifier so concurrent/repeated runs never collide.
RUN_ID = uuid.uuid4().hex[:10]


@pytest.fixture(scope='module')
def string_property(login):
    """A string property created for this test run."""
    from wikibaseintegrator import WikibaseIntegrator
    wbi = WikibaseIntegrator(login=login)

    prop = wbi.property.new(datatype='string')
    prop.labels.set(language='en', value=f'WBI integration test string property {RUN_ID}')
    return prop.write(summary='WikibaseIntegrator integration test setup')


class TestItemLifecycle:
    def test_create_read_update_delete(self, wbi, string_property):
        label = f'WBI integration test item {RUN_ID}'

        # Create
        item = wbi.item.new()
        item.labels.set(language='en', value=label)
        item.descriptions.set(language='en', value='temporary item created by the WikibaseIntegrator test suite')
        item.claims.add(String(prop_nr=string_property.id, value='initial value'))
        written = item.write(summary='WikibaseIntegrator integration test: create')

        assert written.id
        assert written.labels.get('en') == label
        assert written.claims.get(string_property.id)[0].mainsnak.datavalue['value'] == 'initial value'

        # Read back from the instance
        fetched = wbi.item.get(written.id)
        assert fetched.labels.get('en') == label
        assert fetched.lastrevid == written.lastrevid

        # Update: label + a second claim
        # Claims.add() defaults to ActionIfExists.APPEND_OR_REPLACE: the existing claim for this property is kept.
        fetched.labels.set(language='en', value=label + ' (updated)')
        fetched.claims.add(String(prop_nr=string_property.id, value='second value'))
        updated = fetched.write(summary='WikibaseIntegrator integration test: update')

        assert updated.labels.get('en') == label + ' (updated)'
        assert len(updated.claims.get(string_property.id)) == 2
        assert updated.lastrevid > written.lastrevid

        # Delete (requires a user with delete rights, e.g. the docker admin)
        updated.delete(reason='WikibaseIntegrator integration test cleanup')

    def test_get_nonexistent_item(self, wbi):
        # A well-formed but non-existent numeric ID doesn't trigger an API-level error: wbgetentities
        # replies 200 with the entity marked 'missing', which BaseEntity.from_json turns into
        # MissingEntityException. NonExistentEntityError is for the separate no-such-entity/missingtitle
        # API error path (e.g. an invalid site+title lookup).
        with pytest.raises(MissingEntityException):
            wbi.item.get('Q999999999')


class TestClaimsWithQualifiersAndReferences:
    def test_qualifier_and_reference_roundtrip(self, wbi, string_property):
        claim = String(prop_nr=string_property.id, value='qualified value')
        claim.qualifiers.add(String(prop_nr=string_property.id, value='a qualifier'))
        claim.references.add(String(prop_nr=string_property.id, value='a reference'))

        item = wbi.item.new()
        item.labels.set(language='en', value=f'WBI integration test qualified item {RUN_ID}')
        item.claims.add(claim)
        written = item.write(summary='WikibaseIntegrator integration test: qualifiers/references')

        fetched = wbi.item.get(written.id)
        fetched_claim = fetched.claims.get(string_property.id)[0]
        assert fetched_claim.qualifiers.get(string_property.id)[0].datavalue['value'] == 'a qualifier'
        assert len(fetched_claim.references) == 1

        fetched.delete(reason='WikibaseIntegrator integration test cleanup')


@pytest.fixture(scope='module')
def lexeme_prerequisites(login):
    """The items used as language and lexical category of the lexemes created for this test run."""
    from wikibaseintegrator import WikibaseIntegrator
    wbi = WikibaseIntegrator(login=login)

    # The WikibaseLexeme extension is optional on a Wikibase instance
    extensions = mediawiki_api_call_helper(data={'action': 'query', 'meta': 'siteinfo', 'siprop': 'extensions'}, allow_anonymous=True)['query']['extensions']
    if not any(extension.get('name') == 'WikibaseLexeme' for extension in extensions):
        pytest.skip('The WikibaseLexeme extension is not installed on the instance')

    items = {}
    for role in ('language', 'lexical category'):
        item = wbi.item.new()
        item.labels.set(language='en', value=f'WBI integration test {role} {RUN_ID}')
        items[role] = item.write(summary='WikibaseIntegrator integration test setup')

    yield items

    for item in items.values():
        item.delete(reason='WikibaseIntegrator integration test cleanup')


class TestLexemeFormsAndSenses:
    def test_write_form_and_sense(self, wbi, lexeme_prerequisites):
        lexeme = wbi.lexeme.new(language=lexeme_prerequisites['language'].id, lexical_category=lexeme_prerequisites['lexical category'].id)
        lexeme.lemmas.set(language='en', value=f'wbi-lemma-{RUN_ID}')
        lexeme.write(summary='WikibaseIntegrator integration test: create lexeme')
        assert lexeme.id

        # A single Form, with wbladdform
        form = Form(grammatical_features=lexeme_prerequisites['lexical category'].id)
        form.representations.set(language='en', value=f'wbi-form-{RUN_ID}')
        form_id = lexeme.write_form(form)
        assert form_id.startswith(f'{lexeme.id}-F')
        assert form.id == form_id

        # Several Senses at once with wbladdsense, the one marked as removed is skipped
        for gloss in ('first', 'second'):
            sense = Sense()
            sense.glosses.set(language='en', value=f'{gloss} gloss {RUN_ID}')
            lexeme.senses.add(sense)
        removed_sense = Sense()
        removed_sense.glosses.set(language='en', value='removed gloss')
        lexeme.senses.add(removed_sense.remove())

        sense_ids = lexeme.write_senses()
        assert len(sense_ids) == 2
        assert all(sense_id.startswith(f'{lexeme.id}-S') for sense_id in sense_ids)

        # Read back from the instance
        fetched = wbi.lexeme.get(lexeme.id)
        assert fetched.forms.get(form_id).representations.get('en').value == f'wbi-form-{RUN_ID}'
        assert fetched.forms.get(form_id).grammatical_features == [lexeme_prerequisites['lexical category'].id]
        assert [fetched.senses.get(sense_id).glosses.get('en').value for sense_id in sense_ids] == [f'first gloss {RUN_ID}', f'second gloss {RUN_ID}']
        assert len(fetched.senses) == 2

        fetched.delete(reason='WikibaseIntegrator integration test cleanup')

    def test_edit_and_remove_forms_and_senses(self, wbi, lexeme_prerequisites):
        lexical_category = lexeme_prerequisites['lexical category'].id
        lexeme = wbi.lexeme.new(language=lexeme_prerequisites['language'].id, lexical_category=lexical_category)
        lexeme.lemmas.set(language='en', value=f'wbi-edit-lemma-{RUN_ID}')
        for name in ('kept', 'removed'):
            form = Form(grammatical_features=lexical_category)
            form.representations.set(language='en', value=f'wbi-{name}-form-{RUN_ID}')
            lexeme.forms.add(form)
        sense = Sense()
        sense.glosses.set(language='en', value=f'removed gloss {RUN_ID}')
        lexeme.senses.add(sense)
        lexeme_id = lexeme.write(summary='WikibaseIntegrator integration test: create lexeme with forms and senses').id

        # Edit a form, remove the other form and the sense, in a single write()
        fetched = wbi.lexeme.get(lexeme_id)
        assert len(fetched.forms) == 2
        assert len(fetched.senses) == 1
        forms = {form.representations.get('en').value: form for form in fetched.forms}
        kept = forms[f'wbi-kept-form-{RUN_ID}']
        kept.representations.set(language='en', value=f'wbi-edited-form-{RUN_ID}')
        forms[f'wbi-removed-form-{RUN_ID}'].remove()
        next(iter(fetched.senses)).remove()
        fetched.write(summary='WikibaseIntegrator integration test: edit and remove forms and senses')

        result = wbi.lexeme.get(lexeme_id)
        assert [(form.id, form.representations.get('en').value) for form in result.forms] == [(kept.id, f'wbi-edited-form-{RUN_ID}')]
        assert len(result.senses) == 0

        result.delete(reason='WikibaseIntegrator integration test cleanup')

    def test_write_as_new_copies_the_forms_and_senses(self, wbi, lexeme_prerequisites):
        lexical_category = lexeme_prerequisites['lexical category'].id
        lexeme = wbi.lexeme.new(language=lexeme_prerequisites['language'].id, lexical_category=lexical_category)
        lexeme.lemmas.set(language='en', value=f'wbi-copied-lemma-{RUN_ID}')
        form = Form(grammatical_features=lexical_category)
        form.representations.set(language='en', value=f'wbi-copied-form-{RUN_ID}')
        lexeme.forms.add(form)
        sense = Sense()
        sense.glosses.set(language='en', value=f'copied gloss {RUN_ID}')
        lexeme.senses.add(sense)
        original_id = lexeme.write(summary='WikibaseIntegrator integration test: create lexeme to copy').id

        # The forms and senses of the copy are new ones, of the copy (#1208)
        copy_id = wbi.lexeme.get(original_id).write(as_new=True, summary='WikibaseIntegrator integration test: copy lexeme').id
        assert copy_id != original_id

        copy = wbi.lexeme.get(copy_id)
        assert [(form.id, form.representations.get('en').value) for form in copy.forms] == [(f'{copy_id}-F1', f'wbi-copied-form-{RUN_ID}')]
        assert [(sense.id, sense.glosses.get('en').value) for sense in copy.senses] == [(f'{copy_id}-S1', f'copied gloss {RUN_ID}')]

        original = wbi.lexeme.get(original_id)
        assert [form.id for form in original.forms] == [f'{original_id}-F1']

        for entity in (copy, original):
            entity.delete(reason='WikibaseIntegrator integration test cleanup')


class TestSearch:
    def test_search_finds_created_entity(self, wbi, string_property):
        # The property created for this run must be findable by its label.
        results = search_entities(f'WBI integration test string property {RUN_ID}', search_type='property', allow_anonymous=True)
        assert string_property.id in results


class TestLogin:
    def test_wrong_credentials_rejected(self, integration_api_url):
        from wikibaseintegrator import wbi_login

        with pytest.raises(wbi_login.LoginError):
            wbi_login.Login(user='wrong-user', password='wrong-password', mediawiki_api_url=integration_api_url)
