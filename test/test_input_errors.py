"""
The input checks of the public API raise TypeError or ValueError, which python -O keeps, instead of AssertionError.
"""
import pytest

from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.datatypes import (URL, CommonsMedia, EntitySchema, Form, GeoShape, Item, Lexeme, MonolingualText, MusicalNotation, Property, Sense, String, TabularData,
                                          Time)
from wikibaseintegrator.models import Aliases, Claim, LanguageValues, Qualifiers, Reference, References
from wikibaseintegrator.wbi_enums import ActionIfExists


@pytest.mark.parametrize('datatype, value', [
    (CommonsMedia, 1), (EntitySchema, 1.5), (Form, 1), (GeoShape, 1), (Item, 1.5), (Lexeme, 1.5), (MusicalNotation, 1), (Property, 1.5), (Sense, 1), (String, 1),
    (TabularData, 1), (URL, 1),
])
def test_datatype_value_of_another_type(datatype, value):
    with pytest.raises(TypeError, match='Expected str'):
        datatype(value=value, prop_nr='P1')


def test_time_of_another_type():
    with pytest.raises(TypeError, match='Expected str'):
        Time(time=20010101, prop_nr='P1')


@pytest.mark.parametrize('text, language', [(1, 'en'), ('a', 1)])
def test_monolingual_text_of_another_type(text, language):
    with pytest.raises(TypeError, match='Expected str'):
        MonolingualText(text=text, language=language, prop_nr='P1')


def test_aliases_set_rejects_an_invalid_action():
    with pytest.raises(ValueError, match='not a valid action_if_exists'):
        Aliases().set('en', 'a', action_if_exists='keep')


def test_language_values_add_rejects_another_type():
    with pytest.raises(TypeError, match='LanguageValue'):
        LanguageValues().add('a')


@pytest.mark.parametrize('action', [ActionIfExists.APPEND_OR_REPLACE, ActionIfExists.FORCE_APPEND, 'keep'])
def test_language_values_set_rejects_an_unsupported_action(action):
    with pytest.raises(ValueError, match='not a valid action_if_exists'):
        LanguageValues().set('en', 'a', action_if_exists=action)


def test_claim_qualifiers_of_another_type():
    with pytest.raises(TypeError, match='qualifiers'):
        Claim().qualifiers = 'P1'


def test_qualifiers_of_another_type():
    with pytest.raises(TypeError, match='dict'):
        Qualifiers().qualifiers = []


@pytest.mark.parametrize('method', ['add', 'remove'])
def test_qualifier_of_another_type(method):
    with pytest.raises(TypeError, match='Snak or a Claim'):
        getattr(Qualifiers(), method)('P1')


def test_reference_snak_of_another_type():
    with pytest.raises(TypeError, match='Snak or a Claim'):
        Reference().add('P1')


@pytest.mark.parametrize('method', ['add', 'remove'])
def test_reference_of_another_type(method):
    with pytest.raises(TypeError, match='Reference or a Claim'):
        getattr(References(), method)('P1')


def test_generate_entity_instances_of_another_type():
    with pytest.raises(TypeError, match='str or a list'):
        wbi_helpers.generate_entity_instances(entities=('Q1',), allow_anonymous=True)
