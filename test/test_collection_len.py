"""
len(), the iteration and count() of the model collections count the same thing: their elements (#1190).
"""
import pytest

from wikibaseintegrator.datatypes import String
from wikibaseintegrator.models import Aliases, Claims, Form, Forms, LanguageValues, Qualifiers, Reference, References, Sense, Senses, Sitelinks, Snak, Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists


def snak(value):
    return Snak().from_json(String(prop_nr='P1', value=value).get_json()['mainsnak'])


def two_of_p1(kind):
    """The collection holding two values of P1 (two aliases of one language, two values of two languages...)."""
    if kind == 'Claims':
        return Claims().add([String(prop_nr='P1', value='a'), String(prop_nr='P1', value='b')])
    if kind == 'Qualifiers':
        return Qualifiers().add(snak('a')).add(snak('b'))
    if kind == 'Snaks':
        return Snaks().add(snak('a')).add(snak('b'))
    if kind == 'Reference':
        return Reference().add(snak('a')).add(snak('b'))
    if kind == 'References':
        return References().add(Reference().add(snak('a'))).add(Reference().add(snak('b')))
    if kind == 'Aliases':
        return Aliases().add('en', ['a', 'b'])
    if kind == 'Forms':
        return Forms().add(Form(form_id='L1-F1')).add(Form(form_id='L1-F2'))
    if kind == 'Senses':
        return Senses().add(Sense(sense_id='L1-S1')).add(Sense(sense_id='L1-S2'))
    if kind == 'LanguageValues':
        values = LanguageValues()
        values.set('en', 'a')
        values.set('fr', 'b')
        return values
    raise ValueError(kind)


KINDS = ['Claims', 'Qualifiers', 'Snaks', 'Reference', 'References', 'Aliases', 'Forms', 'Senses', 'LanguageValues']


@pytest.mark.parametrize('kind', KINDS)
def test_len_iteration_and_count_agree(kind):
    collection = two_of_p1(kind)
    assert len(collection) == len(list(collection)) == collection.count() == 2


@pytest.mark.parametrize('kind', KINDS)
def test_empty(kind):
    collection = type(two_of_p1(kind))()
    assert len(collection) == collection.count() == 0
    assert not collection


def test_aliases_are_iterable_across_languages():
    aliases = Aliases().add('en', ['a', 'b']).add('fr', 'c')
    assert [(alias.language, alias.value) for alias in aliases] == [('en', 'a'), ('en', 'b'), ('fr', 'c')]
    assert len(aliases) == 3


def test_aliases_marked_for_removal_are_counted():
    # Like the claims: they are still in the collection, until the write
    aliases = Aliases().add('en', ['a', 'b'])
    aliases.set('en', None)
    assert [alias.removed for alias in aliases] == [True, True]
    assert len(aliases) == 2


def test_a_language_without_alias_isnt_counted():
    aliases = Aliases()
    aliases.set('en', None)
    assert aliases.get_json() == {'en': []}
    assert len(aliases) == 0


def test_claims_of_several_properties():
    claims = Claims().add([String(prop_nr='P1', value='a'), String(prop_nr='P2', value='b'), String(prop_nr='P2', value='c')],
                          action_if_exists=ActionIfExists.FORCE_APPEND)
    assert len(claims) == 3


def test_sitelinks():
    sitelinks = Sitelinks()
    sitelinks.set('enwiki', 'Paris')
    sitelinks.set('frwiki', 'Paris')
    assert len(sitelinks) == sitelinks.count() == 2
