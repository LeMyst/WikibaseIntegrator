"""
The validation and error paths of the data types: the invalid values refused by set_value(), the SPARQL values of the
wrong type refused by from_sparql_value(), and the SPARQL value of a claim without a known value.
"""
import pytest

from wikibaseintegrator.datatypes import URL, CommonsMedia, GeoShape, MonolingualText, TabularData
from wikibaseintegrator.wbi_enums import WikibaseSnakType


@pytest.mark.parametrize('datatype,value,message', [
    (CommonsMedia, 'no-extension', 'Invalid CommonsMedia'),
    (URL, 'not a url', 'Invalid URL'),
    (TabularData, 'Data:Population.csv', 'must start with Data: and end with .tab'),
    (TabularData, 'Population.tab', 'must start with Data: and end with .tab'),
    (TabularData, 'Data:Bad|title.tab', 'must start with Data: and end with .tab'),
])
def test_invalid_value(datatype, value, message):
    with pytest.raises(ValueError, match=message):
        datatype(value=value, prop_nr='P1')


@pytest.mark.parametrize('datatype,sparql_value', [
    (CommonsMedia, {'type': 'literal', 'value': 'Example.jpg'}),
    (URL, {'type': 'literal', 'value': 'https://example.org/'}),
    (TabularData, {'type': 'literal', 'value': 'Data:Population.tab'}),
    (MonolingualText, {'type': 'uri', 'value': 'https://example.org/'}),
])
def test_wrong_sparql_type(datatype, sparql_value):
    with pytest.raises(ValueError, match='Wrong SPARQL type'):
        datatype(prop_nr='P1').from_sparql_value(sparql_value)


def test_monolingual_text_without_a_language():
    # Used to raise a KeyError, which the fast run mode doesn't catch, before checking the type
    with pytest.raises(ValueError, match='No language'):
        MonolingualText(prop_nr='P1').from_sparql_value({'type': 'literal', 'value': 'Paris'})


def test_tabular_data_iri_without_a_page():
    with pytest.raises(ValueError, match='Invalid SPARQL value'):
        TabularData(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://commons.wikimedia.org/data/main/Population.csv'})


@pytest.mark.parametrize('datatype', [CommonsMedia, URL, TabularData, GeoShape])
@pytest.mark.parametrize('snaktype', [WikibaseSnakType.UNKNOWN_VALUE, WikibaseSnakType.NO_VALUE])
def test_sparql_value_without_a_known_value(datatype, snaktype):
    # Only a known value has an IRI in the RDF export
    assert datatype(prop_nr='P1', snaktype=snaktype).get_sparql_value() is None
