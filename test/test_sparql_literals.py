"""
The SPARQL string literals of get_sparql_value(): the fast run mode puts them in its queries, where a quote, a backslash
or a line break of the value used to end the literal or make the query invalid.
"""
import pytest

from wikibaseintegrator.datatypes import EDTF, ExternalID, LocalMedia, Math, MonolingualText, MusicalNotation, String
from wikibaseintegrator.datatypes.basedatatype import sparql_string


@pytest.mark.parametrize('text,literal', [
    ('Paris', '"Paris"'),
    ('say "hi"', r'"say \"hi\""'),
    ('a\\b', r'"a\\b"'),
    ('line 1\nline 2', r'"line 1\nline 2"'),
    ('tab\there\r', r'"tab\there\r"'),
    ('\\"', r'"\\\""'),  # the backslash first, then the quote
    ("it's", '"it\'s"'),  # a single quote needs no escape in a double-quoted literal
])
def test_sparql_string(text, literal):
    assert sparql_string(text) == literal


@pytest.mark.parametrize('datatype', [String, ExternalID, MusicalNotation, EDTF, LocalMedia])
def test_string_data_types(datatype):
    assert datatype(value='a "b" \\c', prop_nr='P1').get_sparql_value() == r'"a \"b\" \\c"'


def test_lilypond_score():
    # A MusicalNotation value of Wikidata (P6883), full of backslashes: the query service matched it only escaped
    score = '{\\override Score.BarLine.break-visibility = ##(#f#t#t)\\once\\override Score.BarLine.transparent = ##t}'

    assert MusicalNotation(value=score, prop_nr='P6883').get_sparql_value() == '"' + score.replace('\\', '\\\\') + '"'


def test_monolingual_text():
    # A title of Wikidata (P1476) starting with quotes: MonolingualText escaped the quotes but not the backslashes
    title = MonolingualText(text='"Rural budgeting" \\ landets utveckling', language='sv', prop_nr='P1476')

    assert title.get_sparql_value() == r'"\"Rural budgeting\" \\ landets utveckling"@sv'


def test_math():
    # A TeX formula: "\frac" was read by the endpoint as a form feed (\f) followed by "rac"
    assert Math(value='\\frac{a}{b}', prop_nr='P2534').get_sparql_value() == r'"\\frac{a}{b}"^^<http://www.w3.org/1998/Math/MathML>'
