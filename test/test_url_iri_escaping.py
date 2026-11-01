import pytest

from wikibaseintegrator.datatypes import URL


@pytest.mark.parametrize('url,iri', [
    # Escaped like the RDF export of Wikibase (purtle N3Quoter::escapeIRI)
    ('https://fonts.google.com/?family=Roboto|Open+Sans', '<https://fonts.google.com/?family=Roboto%7COpen+Sans>'),
    ('https://example.org/a{b}c', '<https://example.org/a%7Bb%7Dc>'),
    ('https://example.org/a^b`c', '<https://example.org/a%5Eb%60c>'),
    ('https://example.org/a\\b', '<https://example.org/a%5Cb>'),
    # Unchanged
    ('https://example.org/path?query=1&b=2#fragment', '<https://example.org/path?query=1&b=2#fragment>'),
    ('https://example.org/a%7Cb', '<https://example.org/a%7Cb>'),
])
def test_sparql_value(url, iri):
    assert URL(value=url, prop_nr='P1').get_sparql_value() == iri


def test_value_of_the_query_service_gives_the_same_key():
    """fastrun compares the SPARQL value of a local claim with the one of the claim read from the Query Service."""
    local = URL(value='https://example.org/a|b{c}', prop_nr='P1')
    from_wdqs = URL(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'https://example.org/a%7Cb%7Bc%7D'})

    assert local.get_sparql_value() == from_wdqs.get_sparql_value() == '<https://example.org/a%7Cb%7Bc%7D>'


def test_value_is_not_changed():
    url = URL(value='https://example.org/a|b', prop_nr='P1')
    url.get_sparql_value()

    # Only the SPARQL value is escaped, the value written to Wikibase is kept
    assert url.mainsnak.datavalue['value'] == 'https://example.org/a|b'
