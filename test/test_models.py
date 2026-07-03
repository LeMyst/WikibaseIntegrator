"""
Tests for the entity data models (labels, descriptions, aliases, sitelinks,
claims, qualifiers, references, forms). Entities are built locally from the
JSON fixtures — exactly the payloads a Wikibase instance would return — so no
network interaction is required.
"""
import copy

import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import Item, MonolingualText, String
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.models import Descriptions, Form, Qualifiers
from wikibaseintegrator.wbi_enums import ActionIfExists

from .conftest import load_fixture


@pytest.fixture
def item() -> ItemEntity:
    """A local ItemEntity deserialized from the Q582 fixture."""
    return ItemEntity().from_json(load_fixture('item_Q582'))


class TestDeserialization:
    def test_from_json_roundtrip(self, item):
        fixture = load_fixture('item_Q582')
        assert item.id == 'Q582'
        assert item.type == 'item'
        assert item.lastrevid == fixture['lastrevid']
        assert item.pageid == fixture['pageid']
        assert item.title == 'Q582'

    def test_labels(self, item):
        assert item.labels.get('en') == 'Villeurbanne'
        assert item.labels.get('en').value == 'Villeurbanne'
        assert item.labels.get('es') == 'Villeurbanne'
        assert item.labels.get('ak') is None

    def test_descriptions(self, item):
        description = item.descriptions.get('en').value
        assert len(description) > 3
        assert 'commune' in item.descriptions.get('en')

    def test_aliases(self, item):
        assert 'Villeurbanne (Rhône)' in item.aliases.get('fr')

    def test_claims(self, item):
        assert len(item.claims)
        assert len(item.claims.get('P31')) == 2
        assert 'Q484170' in [claim.mainsnak.datavalue['value']['id'] for claim in item.claims.get('P31')]
        assert item.claims.get(31) == item.claims.get('P31')

    def test_references(self, item):
        assert len(item.claims.get('P2581')[0].references) == 1

    def test_qualifiers(self, item):
        assert len(item.claims.get('P443')[0].qualifiers) == 1

    def test_get_json_returns_same_content(self, item):
        json_data = item.get_json()
        assert json_data['labels']['fr']['value'] == 'Villeurbanne'
        assert json_data['id'] == 'Q582'


class TestLabels:
    def test_set_and_replace(self, item):
        item.labels.set(value='Villeurbanne')
        item.labels.set(value='xfgfdsg')
        item.labels.set(language='en', value='xfgfdsgtest', action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        assert item.get_json()['labels']['fr'] == {'language': 'fr', 'value': 'Villeurbanne'}

    def test_remove_label(self, item):
        item.labels.set(language='fr', value=None)
        item.labels.set(language='non-exist-key', value=None)
        assert 'remove' in item.get_json()['labels']['fr']

    def test_set_label_in_new_language(self, item):
        item.labels.set(value='label', language='ak')
        assert item.labels.get('ak') == 'label'


class TestDescriptions:
    def test_set_and_replace(self, item):
        description = item.descriptions.get('en').value

        item.descriptions.set(value=description)
        assert item.descriptions.get() == description
        item.descriptions.set(value='lorem')
        assert item.descriptions.get() == 'lorem'
        item.descriptions.set(language='es', value='lorem ipsum')
        assert item.descriptions.get('es') == 'lorem ipsum'
        item.descriptions.set(language='en', value='lorem ipsum', action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem'}

    def test_set_on_empty_descriptions(self, item):
        item.descriptions = Descriptions()
        item.descriptions.set(value='')
        item.descriptions.set(language='en', value='lorem ipsum', action_if_exists=ActionIfExists.KEEP)
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}

    def test_keep_and_replace_actions(self, item):
        item.descriptions.set(language='fr', value='lorem', action_if_exists=ActionIfExists.KEEP)
        item.descriptions.set(language='fr', value='lorem ipsum', action_if_exists=ActionIfExists.REPLACE_ALL)
        assert item.get_json()['descriptions']['fr'] == {'language': 'fr', 'value': 'lorem ipsum'}


class TestAliases:
    def test_append_or_replace(self, item):
        item.aliases.set(values=['fake alias'], action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

    def test_alias_actions(self, item):
        item.aliases.set(values=['a'], language='ak', action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
        assert 'a' in item.aliases.get('ak')
        item.aliases.set(values='b', language='ak')
        assert all(i in item.aliases.get('ak') for i in ['a', 'b']) and len(item.aliases.get('ak')) >= 2
        item.aliases.set(values='b', language='ak', action_if_exists=ActionIfExists.REPLACE_ALL)
        assert item.aliases.get('ak') == ['b']
        item.aliases.set(values=['c'], language='ak', action_if_exists=ActionIfExists.REPLACE_ALL)
        assert item.aliases.get('ak') == ['c']
        item.aliases.set(values=['d'], language='ak', action_if_exists=ActionIfExists.KEEP)
        assert 'd' not in item.aliases.get('ak')

    def test_alias_removal(self, item):
        item.aliases.set(values=['a'], language='ak', action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
        item.aliases.set(language='ak', action_if_exists=ActionIfExists.KEEP)
        assert 'remove' not in item.get_json()['aliases']['ak'][0]
        item.aliases.set(language='ak')
        assert 'remove' in item.get_json()['aliases']['ak'][0]


class TestSitelinks:
    def test_get_and_set(self, item):
        assert item.sitelinks.get('enwiki') is not None
        assert item.sitelinks.get('nowiki') is None

        item.sitelinks.set(site='enwiki', title='something')
        assert item.sitelinks.get('enwiki').title == 'something'

    def test_set_on_item_without_sitelinks(self):
        item = ItemEntity()
        assert item.sitelinks.get('enwiki') is None
        item.sitelinks.set(site='enwiki', title='something')
        assert item.sitelinks.get('enwiki').title == 'something'


class TestClaims:
    def test_add_claims_types(self):
        wbi = WikibaseIntegrator()
        ItemEntity(api=wbi)
        wbi.item.new()
        ItemEntity(api=wbi).add_claims(String(value='test', prop_nr='P1'))
        ItemEntity(api=wbi).add_claims([String(value='test', prop_nr='P1')])
        ItemEntity(api=wbi, id='Q2')
        with pytest.raises(TypeError):
            ItemEntity(api=wbi).add_claims('test')

    def test_action_if_exists(self, item):
        instances = [Item(prop_nr='P31', value='Q1234'), Item(prop_nr='P31', value='Q1234')]
        original_claim_count = len(item.claims.get('P31'))

        appended = copy.deepcopy(item)
        appended.add_claims(instances, action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
        claims = [x.mainsnak.datavalue['value']['id'] for x in appended.claims.get('P31')]
        # Only one unique claim is appended
        assert len(claims) == original_claim_count + 1 and claims.count('Q1234') == 1

        forced = copy.deepcopy(item)
        forced.add_claims(instances, action_if_exists=ActionIfExists.FORCE_APPEND)
        claims = [x.mainsnak.datavalue['value']['id'] for x in forced.claims.get('P31')]
        # Both claims are appended, even if identical
        assert len(claims) == original_claim_count + 2 and claims.count('Q1234') == 2

        kept = copy.deepcopy(item)
        kept.add_claims(instances, action_if_exists=ActionIfExists.KEEP)
        claims = [x.mainsnak.datavalue['value']['id'] for x in kept.claims.get('P31')]
        # Claims already exist for P31, nothing is added
        assert len(claims) == original_claim_count and 'Q1234' not in claims

        replaced = copy.deepcopy(item)
        replaced.add_claims(instances, action_if_exists=ActionIfExists.REPLACE_ALL)
        replaced.add_claims(instances, action_if_exists=ActionIfExists.REPLACE_ALL)  # add a second time, in case everything is marked as removed
        claims = [x.mainsnak.datavalue['value']['id'] for x in replaced.claims.get('P31') if not x.removed]
        removed_claims = [True for x in replaced.claims.get('P31') if x.removed]
        # Old claims are marked as removed, only the new unique claim is kept
        assert len(claims) == 1 and 'Q1234' in claims and len(removed_claims) == original_claim_count

    def test_claim_reset_id(self, item):
        claim = item.claims.get('P31')[0]
        assert claim.id is not None
        claim.reset_id()
        assert claim.id is None

    def test_multiline_string_values_rejected(self):
        item = ItemEntity()

        for value in ['Multi\r\nline', 'Multi\rline', 'Multi\nline']:
            with pytest.raises(ValueError):
                item.claims.add(String(prop_nr=123, value=value))
            with pytest.raises(ValueError):
                item.claims.add(MonolingualText(prop_nr=123, text=value))


class TestQualifiers:
    def test_clear(self, item):
        cleared = copy.deepcopy(item)
        assert len(cleared.claims.get('P443')[0].qualifiers.clear('P666')) >= 1
        cleared = copy.deepcopy(item)
        assert len(cleared.claims.get('P443')[0].qualifiers.clear('P407')) == 0
        cleared = copy.deepcopy(item)
        assert len(cleared.claims.get('P443')[0].qualifiers.clear()) == 0

    def test_remove(self, item):
        removed = copy.deepcopy(item)
        assert len(removed.claims.get('P443')[0].qualifiers.remove(Item(prop_nr='P407', value='Q150'))) == 0

    def test_equality(self):
        claim1 = Item(prop_nr='P1')
        claim1.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q2')])
        claim2 = Item(prop_nr='P4')
        claim2.qualifiers.set([Item(prop_nr='P2', value='Q1')])
        claim3 = Item(prop_nr='P4')
        claim3.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q2')])
        claim4 = Item(prop_nr='P4')
        claim4.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q3')])
        claim5 = Item(prop_nr='P4')
        qualifiers = Qualifiers()
        qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q2')])
        claim5.qualifiers.set(qualifiers)

        assert claim1.has_equal_qualifiers(claim2) is False
        assert claim1.has_equal_qualifiers(claim3) is True
        assert claim1.has_equal_qualifiers(claim4) is False
        assert claim1.has_equal_qualifiers(claim5) is True


class TestReferences:
    def test_statement_equality_with_and_without_refs(self):
        oldref = [datatypes.ExternalID(value='P58742', prop_nr='P352'),
                  datatypes.Item(value='Q24784025', prop_nr='P527'),
                  datatypes.Time(time='+2001-12-31T00:00:00Z', prop_nr='P813')]
        olditem = datatypes.Item(value='Q123', prop_nr='P123', references=[oldref])
        newitem = copy.deepcopy(olditem)

        # identical statements
        assert olditem.equals(newitem, include_ref=False)
        assert olditem.equals(newitem, include_ref=True)

        # dates are a month apart
        newitem = copy.deepcopy(olditem)
        newitem.references.remove(datatypes.Time(time='+2001-12-31T00:00:00Z', prop_nr='P813'))
        newitem.references.add(datatypes.Time(time='+2002-01-31T00:00:00Z', prop_nr='P813'))
        assert olditem.equals(newitem, include_ref=False)
        assert not olditem.equals(newitem, include_ref=True)

        # multiple refs
        newitem = copy.deepcopy(olditem)
        newitem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
        assert olditem.equals(newitem, include_ref=False)
        assert not olditem.equals(newitem, include_ref=True)
        olditem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
        assert olditem.equals(newitem, include_ref=True)


class TestForms:
    def test_get_forms(self):
        wbi = WikibaseIntegrator()
        lexeme = wbi.lexeme.new()

        for form_id in ('L5-F4', 'L5-F5', None, None):
            form = Form(form_id=form_id) if form_id else Form()
            form.representations.set(language='en', value='English form representation')
            form.representations.set(language='fr', value='French form representation')
            form.claims.add(datatypes.String(prop_nr='P828', value='Create a string claim for form'))
            lexeme.forms.add(form)

        assert not lexeme.forms.get('L5-F3')
        assert lexeme.forms.get('L5-F4') and lexeme.forms.get('L5-F5')
        assert len(lexeme.forms) == 4


class TestWikibaseIntegratorApi:
    def test_is_bot_propagation(self):
        nwbi = WikibaseIntegrator(is_bot=False)
        assert nwbi.item.api.is_bot is False
        assert ItemEntity(api=nwbi, is_bot=True).api.is_bot is True
        assert ItemEntity(api=nwbi).api.is_bot is False
        assert ItemEntity().api.is_bot is False
