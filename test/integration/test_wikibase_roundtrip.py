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

from wikibaseintegrator.datatypes import Item, String
from wikibaseintegrator.models import Form, Sense
from wikibaseintegrator.wbi_enums import ActionIfExists
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
        # Claims.add() defaults to ActionIfExists.REPLACE_ALL, which would replace (remove)
        # the existing claim for this property instead of adding a second one.
        fetched.labels.set(language='en', value=label + ' (updated)')
        fetched.claims.add(String(prop_nr=string_property.id, value='second value'), action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
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
