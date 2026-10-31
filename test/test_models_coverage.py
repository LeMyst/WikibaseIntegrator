"""
Tests covering the less used paths of the entity data models: the error cases, the lookups that find nothing, the
special operators and a few documented quirks. The models are pure data structures, so no network interaction
is required.
"""
import pytest

from wikibaseintegrator.datatypes import Item, String, Time
from wikibaseintegrator.models import Aliases, Claim, Claims, Form, Forms, Glosses, LanguageValue, LanguageValues, Qualifiers, Reference, References, Sense, Senses, Snak, Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseRank


def _reference(value: str) -> Reference:
    return Reference(snaks=Snaks().add(Snak().from_json(String(prop_nr='P854', value=value).get_json()['mainsnak'])))


class TestAliases:
    def test_init_with_language_and_value(self):
        aliases = Aliases(language='fr', value='alias')
        assert aliases.get('fr') == ['alias']
        assert aliases.get_json() == {'fr': [{'language': 'fr', 'value': 'alias'}]}

    def test_get_without_language_returns_all_aliases(self):
        aliases = Aliases().add('fr', ['a', 'b']).add('en', 'c')
        assert [alias.value for alias in aliases.get()] == ['a', 'b', 'c']

    def test_get_unknown_language(self):
        assert Aliases().add('fr', 'a').get('de') is None

    def test_set_rejects_other_types(self):
        with pytest.raises(TypeError):
            Aliases().set('fr', values=5)

    def test_set_keep_on_empty_language_adds_every_value(self):
        aliases = Aliases().set('fr', values=['a', 'b'], action_if_exists=ActionIfExists.KEEP)
        assert [alias.value for alias in aliases.get('fr')] == ['a', 'b']

    def test_set_keep_on_existing_language_does_nothing(self):
        aliases = Aliases().add('fr', 'a').set('fr', values=['b', 'c'], action_if_exists=ActionIfExists.KEEP)
        assert [alias.value for alias in aliases.get('fr')] == ['a']

    @pytest.mark.parametrize('action', [ActionIfExists.FORCE_APPEND, ActionIfExists.MERGE_REFS_OR_APPEND])
    def test_set_with_unsupported_action_does_nothing(self, action):
        # Only APPEND_OR_REPLACE, REPLACE_ALL and KEEP are implemented for the aliases
        aliases = Aliases().add('fr', 'a').set('fr', values='b', action_if_exists=action)
        assert aliases.get('fr') == ['a']

    def test_get_json_of_an_empty_language(self):
        aliases = Aliases()
        aliases.set('fr', values=None)
        assert aliases.get_json() == {'fr': []}


class TestClaim:
    def test_references_object(self):
        references = References().add(_reference('https://example.org'))
        claim = Claim(references=references)
        assert claim.references is references

    def test_references_list_of_references(self):
        reference = _reference('https://example.org')
        claim = Claim(references=[reference])
        assert list(claim.references) == [reference]
        assert claim.references.references[0] is reference

    def test_references_list_of_lists_rejects_other_objects(self):
        with pytest.raises(ValueError):
            Claim(references=[['not a claim']])

    def test_references_list_of_other_objects(self):
        # Known quirk: an item of the list that is neither a Claim, a list nor a Reference gives an empty reference
        claim = Claim(references=['not a claim'])
        assert len(claim.references) == 1
        assert len(claim.references.references[0]) == 0

    def test_references_of_another_type(self):
        with pytest.raises(ValueError):
            Claim(references='not a list')

    def test_removed_claim_without_id_has_no_remove_flag(self):
        claim = String(prop_nr='P31', value='a')
        claim.remove()
        assert claim.removed
        assert 'remove' not in claim.get_json()

        claim.id = 'Q1$1'
        assert claim.get_json()['remove'] == ''

    def test_contains(self):
        claim = Item(prop_nr='P31', value='Q5')
        assert Item(prop_nr='P31', value='Q5') in claim
        assert Item(prop_nr='P31', value='Q6') not in claim
        # Known quirk: a string is compared with the datavalue, a dict, so it never matches
        assert 'Q5' not in claim
        assert 5 not in claim

    def test_eq_with_a_property_number(self):
        claim = Item(prop_nr='P31', value='Q5')
        assert claim == 'P31'
        assert claim != 'P32'
        assert claim.__eq__(5) is NotImplemented

    def test_equals_with_references(self):
        claim = Item(prop_nr='P31', value='Q5', references=[_reference('https://example.org')])
        same = Item(prop_nr='P31', value='Q5', references=[_reference('https://example.org')])
        other_refs = Item(prop_nr='P31', value='Q5', references=[_reference('https://example.com')])
        other_value = Item(prop_nr='P31', value='Q6', references=[_reference('https://example.org')])

        assert claim.equals(same, include_ref=True)
        assert not claim.equals(other_refs, include_ref=True)
        assert not claim.equals(other_value, include_ref=True)
        assert claim.equals(other_refs)

    def test_equals_with_a_reference_function(self):
        calls = []

        def fref(olditem, newitem):
            calls.append((olditem, newitem))
            return False

        claim = Item(prop_nr='P31', value='Q5')
        same = Item(prop_nr='P31', value='Q5')
        assert not claim.equals(same, include_ref=True, fref=fref)
        assert calls == [(claim, same)]

        # The function isn't called when the claims differ
        assert not claim.equals(Item(prop_nr='P31', value='Q6'), include_ref=True, fref=fref)
        assert len(calls) == 1

    def test_base_get_sparql_value(self):
        assert Claim().get_sparql_value() is None

    def test_rank(self):
        claim = Claim(rank=WikibaseRank.PREFERRED)
        assert claim.rank == WikibaseRank.PREFERRED
        with pytest.raises(ValueError):
            claim.rank = 'unknown'


class TestClaims:
    def test_remove_unknown_property(self):
        claims = Claims().add(String(prop_nr='P1', value='a'))
        claims.remove('P2')
        assert [claim.mainsnak.property_number for claim in claims] == ['P1']

    def test_add_rejects_an_invalid_action(self):
        # On Python 3.11 to 3.13, `'replace' in ActionIfExists` raised a TypeError instead of returning False
        with pytest.raises(ValueError, match='is not a valid action_if_exists value'):
            Claims().add(String(prop_nr='P1', value='a'), action_if_exists='replace')

    def test_add_skips_none(self):
        # A Claims object holding None (only possible by editing its dict) is skipped, whatever the action
        source = Claims()
        source.claims = {'P1': [None]}
        for action in ActionIfExists:
            claims = Claims().add(source, action_if_exists=action)
            assert not claims.claims

    def test_add_replace_all_on_a_new_property(self):
        claims = Claims().add(String(prop_nr='P1', value='a'))
        claims.add(String(prop_nr='P2', value='b'), action_if_exists=ActionIfExists.REPLACE_ALL)
        assert [claim.mainsnak.datavalue['value'] for claim in claims] == ['a', 'b']
        assert not any(claim.removed for claim in claims)

    def test_add_merge_refs_with_a_reference_already_present(self):
        claims = Claims().add(String(prop_nr='P1', value='a', references=[_reference('https://example.org')]))
        claims.add(String(prop_nr='P1', value='a', references=[_reference('https://example.org')]), action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)
        assert claims.count() == 1
        assert list(claims.get('P1')[0].references) == [_reference('https://example.org')]

    def test_add_merge_refs_adds_only_the_missing_references(self):
        claims = Claims().add(String(prop_nr='P1', value='a', references=[_reference('https://example.org')]))
        new_claim = String(prop_nr='P1', value='a', references=[_reference('https://example.org'), _reference('https://example.com')])
        with pytest.warns(UserWarning, match='more or less than 1 reference block'):
            claims.add(new_claim, action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)
        assert claims.count() == 1
        assert list(claims.get('P1')[0].references) == [_reference('https://example.org'), _reference('https://example.com')]

    def test_get_json_skips_the_removed_claims_without_id(self):
        claims = Claims().add([String(prop_nr='P1', value='a'), String(prop_nr='P2', value='b')])
        removed = String(prop_nr='P2', value='c')
        claims.add(removed)
        removed.remove()
        claims.get('P1')[0].remove()

        # P1 has no claim left to send, P2 keeps the claim that isn't removed
        json_data = claims.get_json()
        assert list(json_data) == ['P2']
        assert [claim['mainsnak']['datavalue']['value'] for claim in json_data['P2']] == ['b']

    def test_len_counts_properties(self):
        claims = Claims().add([String(prop_nr='P1', value='a'), String(prop_nr='P1', value='b')])
        assert len(claims) == 1
        assert claims.count() == 2


class TestForms:
    def test_grammatical_features_rejects_a_bool(self):
        with pytest.raises(TypeError):
            Form(grammatical_features=True)

    def test_grammatical_features_set_to_none(self):
        form = Form(grammatical_features='Q1')
        form.grammatical_features = None
        assert form.grammatical_features == []

    def test_get_duplicate_id(self):
        forms = Forms().add(Form(form_id='L1-F1')).add(Form(form_id='L1-F1'))
        with pytest.raises(ValueError):
            forms.get('L1-F1')

    def test_get(self):
        form = Form(form_id='L1-F1')
        forms = Forms().add(form)
        assert forms.get('L1-F1') is form
        assert forms.get('L1-F2') is None


class TestLanguageValue:
    @pytest.mark.parametrize('language', [None, '', 5])
    def test_invalid_language(self, language):
        with pytest.raises(ValueError):
            LanguageValue(language=language)

    def test_eq(self):
        assert LanguageValue('fr', 'a') == LanguageValue('fr', 'a')
        assert LanguageValue('fr', 'a') != LanguageValue('en', 'a')
        assert LanguageValue('fr', 'a') != LanguageValue('fr', 'b')
        assert LanguageValue('fr', 'a') == 'a'

    def test_language_values_iter_and_len(self):
        values = LanguageValues()
        values.set('fr', 'a')
        values.set('en', 'b')
        assert len(values) == 2
        assert [value.value for value in values] == ['a', 'b']
        assert 'fr' in values
        assert 'de' not in values


class TestQualifiers:
    def test_set_none_clears(self):
        qualifiers = Qualifiers().add(String(prop_nr='P1', value='a'))
        qualifiers.set(None)
        assert len(qualifiers) == 0

    def test_set_dict(self):
        snaks = {'P1': [Snak(property_number='P1')]}
        qualifiers = Qualifiers().set(snaks)
        assert qualifiers.qualifiers is snaks

    def test_get(self):
        qualifiers = Qualifiers().add(String(prop_nr='P1', value='a'))
        assert [snak.datavalue['value'] for snak in qualifiers.get(1)] == ['a']
        assert qualifiers.get('P1') == qualifiers.get(1)
        assert qualifiers.get('P2') == []

    def test_add_none(self):
        # The None guard of add() only skips the type check, the property lookup that follows fails
        with pytest.raises(AttributeError):
            Qualifiers().add(None)

    def test_remove_a_snak(self):
        qualifiers = Qualifiers().add(String(prop_nr='P1', value='a')).add(String(prop_nr='P1', value='b'))
        snak = Snak().from_json(String(prop_nr='P1', value='a').get_json()['mainsnak'])
        qualifiers.remove(snak)
        assert [snak.datavalue['value'] for snak in qualifiers.get('P1')] == ['b']

    def test_remove_none(self):
        with pytest.raises(AttributeError):
            Qualifiers().remove(None)

    def test_clear_with_an_int(self):
        qualifiers = Qualifiers().add(String(prop_nr='P1', value='a')).add(String(prop_nr='P2', value='b'))
        qualifiers.clear(1)
        assert list(qualifiers.qualifiers) == ['P2']


class TestReferences:
    def test_reference_eq_with_another_type(self):
        reference = _reference('https://example.org')
        assert reference.__eq__('https://example.org') is NotImplemented
        assert reference != 'https://example.org'

    def test_remove_a_reference(self):
        references = References().add(_reference('https://example.org')).add(_reference('https://example.com'))
        assert references.remove(_reference('https://example.org'))
        assert list(references) == [_reference('https://example.com')]
        assert not references.remove(_reference('https://example.org'))


class TestSenses:
    def test_removed_sense(self):
        sense = Sense(sense_id='L1-S1', glosses=Glosses().add(LanguageValue('en', 'a')))
        sense.removed = True
        assert sense.get_json()['remove'] == ''

    def test_get_and_len(self):
        first = Sense(sense_id='L1-S1')
        second = Sense(sense_id='L1-S2')
        senses = Senses().add(first).add(second)
        assert len(senses) == 2
        assert senses.get('L1-S2') is second
        assert senses.get('L1-S3') is None


class TestSnaks:
    def test_invalid_property_number(self):
        with pytest.raises(ValueError):
            Snak(property_number='Q1')

    def test_hash(self):
        snak = Snak().from_json({'snaktype': 'novalue', 'property': 'P1', 'hash': 'abc'})
        assert snak.hash == 'abc'

    def test_snak_eq_with_another_type(self):
        snak = Snak(property_number='P1')
        assert snak.__eq__('P1') is NotImplemented
        assert snak != 'P1'

    def test_get(self):
        snak = Snak(property_number='P1')
        snaks = Snaks().add(snak)
        assert snaks.get(1) == [snak]
        assert snaks.get('P1') == [snak]
        assert snaks.get('P2') == []


class TestEnumArguments:
    """A value that isn't a member of the enum is rejected the same way on every Python version (3.11 to 3.13 raised a TypeError)."""

    def test_aliases_set_rejects_an_invalid_action(self):
        with pytest.raises(AssertionError):
            Aliases().set('en', 'a', action_if_exists='keep')

    def test_time_rejects_a_precision_of_another_type(self):
        with pytest.raises(ValueError, match='Invalid value for time precision'):
            Time(time='+2001-00-00T00:00:00Z', precision='year', prop_nr='P1')
