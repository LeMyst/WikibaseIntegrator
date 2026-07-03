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
from wikibaseintegrator.wbi_exceptions import NonExistentEntityError
from wikibaseintegrator.wbi_helpers import search_entities

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
        fetched.labels.set(language='en', value=label + ' (updated)')
        fetched.claims.add(String(prop_nr=string_property.id, value='second value'))
        updated = fetched.write(summary='WikibaseIntegrator integration test: update')

        assert updated.labels.get('en') == label + ' (updated)'
        assert len(updated.claims.get(string_property.id)) == 2
        assert updated.lastrevid > written.lastrevid

        # Delete (requires a user with delete rights, e.g. the docker admin)
        updated.delete(reason='WikibaseIntegrator integration test cleanup')

    def test_get_nonexistent_item(self, wbi):
        with pytest.raises(NonExistentEntityError):
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
