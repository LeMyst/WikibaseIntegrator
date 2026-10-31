"""
The paths of the data types not covered elsewhere: the legacy parse_sparql_value() methods, the generic
from_sparql_value() of BaseDataType, the invalid values and SPARQL values refused by each data type, and the SPARQL value
of a claim without a known value.
"""
import pytest

from wikibaseintegrator.datatypes import (URL, BaseDataType, CommonsMedia, EntitySchema, ExternalID, Form, GeoShape, GlobeCoordinate, Item, Lexeme, Math, MonolingualText,
                                          Property, Quantity, Sense, String, Time)
from wikibaseintegrator.wbi_enums import WikibaseSnakType, WikibaseTimePrecision

DECIMAL = 'http://www.w3.org/2001/XMLSchema#decimal'
DATETIME = 'http://www.w3.org/2001/XMLSchema#dateTime'
WKT = 'http://www.opengis.net/ont/geosparql#wktLiteral'


class TestBaseDataType:
    @pytest.mark.parametrize('prop_nr', ['http://www.wikidata.org/entity/P31', 'http://www.wikidata.org/prop/direct/P31', 'P31'])
    def test_property_number_from_a_uri(self, prop_nr):
        # A property given by its URI is reduced to its ID
        assert BaseDataType(prop_nr=prop_nr).mainsnak.property_number == 'P31'

    def test_set_value_is_a_no_op(self):
        claim = BaseDataType(prop_nr='P1')
        claim.set_value('anything')
        assert claim.mainsnak.datavalue == {}

    def test_from_sparql_value_literal(self):
        # The generic implementation, inherited by a data type whose RDF value is the literal itself
        claim = String(prop_nr='P1')
        assert BaseDataType.from_sparql_value(claim, {'type': 'literal', 'value': 'Paris'}) is claim
        assert claim.mainsnak.datavalue == {'value': 'Paris', 'type': 'string'}
        assert claim.mainsnak.snaktype == WikibaseSnakType.KNOWN_VALUE

    def test_from_sparql_value_of_a_base_data_type(self):
        # The class kept for an unknown datatype: the literal is accepted, but its set_value() stores nothing
        claim = BaseDataType(prop_nr='P1')
        assert claim.from_sparql_value({'type': 'literal', 'value': 'Paris'}) is claim
        assert claim.mainsnak.datavalue == {}

    @pytest.mark.parametrize('sparql_value', [
        {'type': 'bnode', 'value': 't123'},
        {'type': 'uri', 'value': 'http://www.wikidata.org/.well-known/genid/0123456789abcdef'},
    ])
    def test_from_sparql_value_unknown_value(self, sparql_value):
        claim = BaseDataType(prop_nr='P1')
        assert claim.from_sparql_value(sparql_value) is claim
        assert claim.mainsnak.snaktype == WikibaseSnakType.UNKNOWN_VALUE

    def test_from_sparql_value_wrong_type(self):
        with pytest.raises(ValueError, match='Wrong SPARQL type uri'):
            BaseDataType(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://example.org/'})

    @pytest.mark.parametrize('datatype', [String, ExternalID])
    @pytest.mark.parametrize('value,type,expected', [
        ('"Paris"', 'literal', 'Paris'),
        ('Paris', 'literal', 'Paris'),
        ('<http://example.org/Paris>', 'uri', 'http://example.org/Paris'),
        ('http://example.org/Paris', 'uri', 'http://example.org/Paris'),
    ])
    def test_parse_sparql_value(self, datatype, value, type, expected):
        claim = datatype(prop_nr='P1')
        assert claim.parse_sparql_value(value, type=type) is True
        assert claim.mainsnak.datavalue == {'value': expected, 'type': 'string'}

    @pytest.mark.parametrize('type', ['literal', 'uri'])
    def test_parse_sparql_value_no_match(self, type):
        # '.' doesn't match a line break, so a value spanning two lines doesn't match the patterns
        claim = String(prop_nr='P1')
        assert claim.parse_sparql_value('line 1\nline 2', type=type) is False
        assert claim.mainsnak.datavalue == {}

    def test_parse_sparql_value_unknown_type(self):
        with pytest.raises(ValueError):
            String(prop_nr='P1').parse_sparql_value('Paris', type='bnode')


class TestParseSparqlValue:
    """The legacy parse_sparql_value() of the data types overriding it"""

    @pytest.mark.parametrize('value', ['<http://commons.wikimedia.org/wiki/Special:FilePath/Example%20file.jpg>', 'Example%20file.jpg'])
    def test_commons_media(self, value):
        claim = CommonsMedia(prop_nr='P1')
        assert claim.parse_sparql_value(value) is True
        assert claim.mainsnak.datavalue['value'] == 'Example file.jpg'

    def test_commons_media_no_match(self):
        claim = CommonsMedia(prop_nr='P1')
        # The file name can hold a line break ([^/] matches it), but the part before the last '/' can't ('.' doesn't)
        assert claim.parse_sparql_value('line 1\nhttp://example.org/Example.jpg') is False
        assert claim.mainsnak.datavalue == {}

    @pytest.mark.parametrize('value', ['"Point(2.35 48.85)"^^geo:wktLiteral', 'Point(2.35 48.85)'])
    def test_globe_coordinate(self, value):
        claim = GlobeCoordinate(prop_nr='P1')
        assert claim.parse_sparql_value(value) is True
        assert claim.mainsnak.datavalue['value']['longitude'] == 2.35
        assert claim.mainsnak.datavalue['value']['latitude'] == 48.85

    def test_globe_coordinate_no_match(self):
        claim = GlobeCoordinate(prop_nr='P1')
        assert claim.parse_sparql_value('Paris') is False
        assert claim.mainsnak.datavalue == {}

    def test_monolingual_text(self):
        claim = MonolingualText(prop_nr='P1')
        assert claim.parse_sparql_value('"Paris"@fr') is True
        assert claim.mainsnak.datavalue['value'] == {'text': 'Paris', 'language': 'fr'}

    def test_monolingual_text_no_match(self):
        claim = MonolingualText(prop_nr='P1')
        assert claim.parse_sparql_value('Paris') is False
        assert claim.mainsnak.datavalue == {}

    def test_quantity(self):
        claim = Quantity(prop_nr='P1')
        assert claim.parse_sparql_value('12.5', unit='http://www.wikidata.org/entity/Q11573') is True
        assert claim.mainsnak.datavalue['value'] == {'amount': '+12.5', 'unit': 'http://www.wikidata.org/entity/Q11573'}

    @pytest.mark.parametrize('value', ['<https://example.org/>', 'https://example.org/'])
    def test_url(self, value):
        claim = URL(prop_nr='P1')
        assert claim.parse_sparql_value(value) is True
        assert claim.mainsnak.datavalue['value'] == 'https://example.org/'

    def test_url_no_match(self):
        claim = URL(prop_nr='P1')
        assert claim.parse_sparql_value('https://example.org/\nhttps://example.com/') is False
        assert claim.mainsnak.datavalue == {}


@pytest.mark.parametrize('datatype,value,message', [
    (EntitySchema, 'Q10', 'Invalid Entity Schema ID'),
    (Form, 'L5-S1', 'Invalid form ID'),
    (GeoShape, 'Paris.map', 'must start with Data: and end with .map'),
    (Item, 'P31', 'Invalid item ID'),
    (Lexeme, 'Q5', 'Invalid lexeme ID'),
    (Property, 'Q5', 'Invalid property ID'),
    (Sense, 'L5-F1', 'Invalid sense ID'),
])
def test_invalid_value(datatype, value, message):
    with pytest.raises(ValueError, match=message):
        datatype(value=value, prop_nr='P1')


@pytest.mark.parametrize('datatype,sparql_value', [
    (EntitySchema, {'type': 'literal', 'value': 'E10'}),
    (Form, {'type': 'literal', 'value': 'L5-F1'}),
    (GeoShape, {'type': 'literal', 'value': 'Data:Paris.map'}),
    (Item, {'type': 'literal', 'value': 'Q5'}),
    (Lexeme, {'type': 'literal', 'value': 'L5'}),
    (Sense, {'type': 'literal', 'value': 'L5-S1'}),
    (GlobeCoordinate, {'datatype': WKT, 'type': 'uri', 'value': 'Point(2.35 48.85)'}),
    (Quantity, {'datatype': DECIMAL, 'type': 'uri', 'value': '12'}),
    (Time, {'datatype': DATETIME, 'type': 'uri', 'value': '+2020-01-01T00:00:00Z'}),
])
def test_wrong_sparql_type(datatype, sparql_value):
    with pytest.raises(ValueError, match='Wrong SPARQL type'):
        datatype(prop_nr='P1').from_sparql_value(sparql_value)


@pytest.mark.parametrize('datatype,sparql_value', [
    (GlobeCoordinate, {'datatype': DECIMAL, 'type': 'literal', 'value': 'Point(2.35 48.85)'}),
    (Math, {'datatype': 'http://www.w3.org/2001/XMLSchema#string', 'type': 'literal', 'value': 'c^2=a^2+b^2'}),
    (Math, {'type': 'literal', 'value': 'c^2=a^2+b^2'}),
    (Quantity, {'datatype': DATETIME, 'type': 'literal', 'value': '12'}),
    (Time, {'datatype': DECIMAL, 'type': 'literal', 'value': '+2020-01-01T00:00:00Z'}),
])
def test_wrong_sparql_datatype(datatype, sparql_value):
    with pytest.raises(ValueError, match='Wrong SPARQL datatype'):
        datatype(prop_nr='P1').from_sparql_value(sparql_value)


@pytest.mark.parametrize('datatype,sparql_value', [
    (EntitySchema, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q10'}),
    (Form, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/L5-S1'}),
    (Item, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/E10'}),
    (Lexeme, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q5'}),
    (Property, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q5'}),
    (Sense, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/L5-F1'}),
    (GlobeCoordinate, {'datatype': WKT, 'type': 'literal', 'value': 'Point(2.35)'}),
])
def test_invalid_sparql_value(datatype, sparql_value):
    with pytest.raises(ValueError, match='Invalid SPARQL value'):
        datatype(prop_nr='P1').from_sparql_value(sparql_value)


@pytest.mark.parametrize('datatype', [EntitySchema, Form, Item, Lexeme, Property, Sense])
@pytest.mark.parametrize('snaktype', [WikibaseSnakType.UNKNOWN_VALUE, WikibaseSnakType.NO_VALUE])
def test_no_sparql_value_without_a_known_value(datatype, snaktype):
    assert datatype(prop_nr='P1', snaktype=snaktype).get_sparql_value() is None


def test_entity_schema_numeric_id():
    claim = EntitySchema(value=10, prop_nr='P1')
    assert claim.mainsnak.datavalue['value'] == {'entity-type': 'entity-schema', 'id': 'E10'}
    assert claim.get_sparql_value(wikibase_url='https://example.org') == '<https://example.org/entity/E10>'


class TestQuantity:
    def test_amount_not_a_number_once_formatted(self):
        # float() accepts the leading space, format_amount() then puts the '+' before it, which float() refuses
        with pytest.raises(ValueError, match='must parse as integers or float'):
            Quantity(amount=' 0.5', prop_nr='P1')

    @pytest.mark.parametrize('lower_bound,upper_bound', [(6, 7), (4, 3)])
    def test_lower_bound_too_large(self, lower_bound, upper_bound):
        # Above the amount or above the upper bound
        with pytest.raises(ValueError, match='Lower bound too large'):
            Quantity(amount=5, lower_bound=lower_bound, upper_bound=upper_bound, prop_nr='P1')

    def test_upper_bound_too_small(self):
        with pytest.raises(ValueError, match='Upper bound too small'):
            Quantity(amount=5, upper_bound=4, prop_nr='P1')


class TestTime:
    def test_calendar_model_id(self):
        claim = Time(time='+2020-01-01T00:00:00Z', calendarmodel='Q1985727', wikibase_url='https://example.org', prop_nr='P1')
        assert claim.mainsnak.datavalue['value']['calendarmodel'] == 'https://example.org/entity/Q1985727'

    def test_precision_not_a_time_precision(self):
        # Neither an int nor a WikibaseTimePrecision: refused before choosing the pattern
        with pytest.raises(ValueError, match='Invalid value for time precision'):
            Time(time='+2020-01-01T00:00:00Z', precision=WikibaseSnakType.KNOWN_VALUE, prop_nr='P1')

    @pytest.mark.parametrize('time,precision', [
        ('+2020-05-00T00:00:00Z', WikibaseTimePrecision.DAY),
        ('+2020-00-00T00:00:00Z', WikibaseTimePrecision.MONTH),
        ('+2020-01-01T12:00:00Z', WikibaseTimePrecision.YEAR),
    ])
    def test_time_inconsistent_with_the_precision(self, time, precision):
        with pytest.raises(ValueError, match='consistent with the introduced precision'):
            Time(time=time, precision=precision, prop_nr='P1')

    @pytest.mark.parametrize('time', ['2020', '+2020-01-01', ''])
    def test_sparql_time_not_a_timestamp(self, time):
        # Returned unchanged
        assert Time.sparql_time(time, WikibaseTimePrecision.YEAR) == time

    def test_unparsable_time(self):
        claim = Time(time='+2020-01-01T00:00:00Z', prop_nr='P1')
        claim.mainsnak.datavalue['value']['time'] = 'not a time'
        with pytest.raises(ValueError, match="Unable to parse time value 'not a time'"):
            claim.get_year()
