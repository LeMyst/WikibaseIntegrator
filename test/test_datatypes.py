"""
Serialization tests for the datatypes: they validate that the JSON produced
locally by the library matches what a Wikibase instance expects. No network
interaction is involved.
"""
import itertools

import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import (URL, BaseDataType, CommonsMedia, EntitySchema, ExternalID, Form, GeoShape, GlobeCoordinate, Item, Lexeme, Math, MonolingualText,
                                          MusicalNotation, Property, Quantity, Sense, String, TabularData, Time)
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
from wikibaseintegrator.datatypes.time import GREGORIAN_CALENDAR, JULIAN_CALENDAR
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseRank, WikibaseSnakType, WikibaseTimePrecision
from wikibaseintegrator.wbi_exceptions import UnknownDatatypeError


class TestQuantity:
    def test_amount_normalization(self):
        dt = Quantity(amount='34.5', prop_nr='P43')

        dt_json = dt.get_json()
        assert dt_json['mainsnak']['datatype'] == WikibaseDatatype.QUANTITY.value

        value = dt_json['mainsnak']['datavalue']
        assert value['value']['amount'] == '+34.5'
        assert value['value']['unit'] == '1'

    def test_bounds_and_unit(self):
        dt = Quantity(amount='34.5', prop_nr='P43', upper_bound='35.3', lower_bound='33.7', unit='Q11573')

        value = dt.get_json()['mainsnak']['datavalue']
        assert value['value']['amount'] == '+34.5'
        assert value['value']['unit'] == 'http://www.wikidata.org/entity/Q11573'
        assert value['value']['upperBound'] == '+35.3'
        assert value['value']['lowerBound'] == '+33.7'


class TestGeoShape:
    def test_json(self):
        dt = GeoShape(value='Data:Inner_West_Light_Rail_stops.map', prop_nr='P43')

        dt_json = dt.get_json()
        assert dt_json['mainsnak']['datatype'] == WikibaseDatatype.GEOSHAPE.value
        assert dt_json['mainsnak']['datavalue']['value'] == 'Data:Inner_West_Light_Rail_stops.map'
        assert dt_json['mainsnak']['datavalue']['type'] == 'string'


class TestGlobeCoordinate:
    def test_equality_does_not_mutate_values(self):
        latitude = 1.234567891
        coordinate1 = GlobeCoordinate(latitude=latitude, longitude=2.3456789, precision=1e-9, prop_nr='P10')
        coordinate2 = GlobeCoordinate(latitude=latitude, longitude=2.3456789, precision=1e-9, prop_nr='P10')

        # Equality is checked on rounded values, but the claims themselves must keep their full precision
        assert coordinate1 == coordinate2
        assert coordinate1.mainsnak.datavalue['value']['latitude'] == latitude

    def test_equality_with_valueless_claim(self):
        coordinate = GlobeCoordinate(latitude=1.5, longitude=2.5, prop_nr='P10')

        assert coordinate != GlobeCoordinate(prop_nr='P10')
        assert coordinate != Item(value='Q123', prop_nr='P10')

    # (longitude, latitude, globe, the WKT literal returned by the Wikidata Query Service for the statement)
    query_service_literals = [
        (2.352222222222222, 48.85666666666667, None, 'Point(2.352222222 48.856666666)'),  # Q90: truncated to 9 decimals
        (-46.633947222222, -23.550394444444, None, 'Point(-46.633947222 -23.550394444)'),  # Q174: truncated toward zero
        (2, 47, None, 'Point(2.0 47.0)'),  # Q142: Java's Double.toString()
        (0, -90, None, 'Point(0.0 -90.0)'),  # Q51
        (4.835, 45.7675, None, 'Point(4.835 45.7675)'),  # Q456
        (354.5, -1.9, 'http://www.wikidata.org/entity/Q111', '<http://www.wikidata.org/entity/Q111> Point(354.5 -1.9)'),  # Q4804701, on Mars
        (0.0005, -0.00012, None, 'Point(5.0E-4 -1.2E-4)'),  # the scientific notation of Java below 10^-3
    ]

    @pytest.mark.parametrize('longitude,latitude,globe,literal', query_service_literals)
    def test_sparql_value_like_the_query_service(self, longitude, latitude, globe, literal):
        coordinate = GlobeCoordinate(latitude=latitude, longitude=longitude, globe=globe, prop_nr='P625')

        assert coordinate.get_sparql_value() == f'"{literal}"^^geo:wktLiteral'

    @pytest.mark.parametrize('longitude,latitude,globe,literal', query_service_literals)
    def test_sparql_value_round_trip(self, longitude, latitude, globe, literal):
        sparql_value = {'datatype': 'http://www.opengis.net/ont/geosparql#wktLiteral', 'type': 'literal', 'value': literal}

        parsed = GlobeCoordinate(prop_nr='P625').from_sparql_value(sparql_value)

        assert parsed.mainsnak.datavalue['value']['globe'] == (globe or 'http://www.wikidata.org/entity/Q2')
        assert parsed.get_sparql_value() == GlobeCoordinate(latitude=latitude, longitude=longitude, globe=globe, prop_nr='P625').get_sparql_value()

    def test_sparql_value_escapes_the_globe_iri(self):
        # Like Wikibase, a '>' of the globe IRI is written '%3E' to keep the WKT literal valid
        coordinate = GlobeCoordinate(latitude=1.5, longitude=2.5, globe='http://example.org/globe>1', prop_nr='P625')
        sparql_value = {'datatype': 'http://www.opengis.net/ont/geosparql#wktLiteral', 'type': 'literal', 'value': '<http://example.org/globe%3E1> Point(2.5 1.5)'}

        assert coordinate.get_sparql_value() == '"<http://example.org/globe%3E1> Point(2.5 1.5)"^^geo:wktLiteral'
        assert GlobeCoordinate(prop_nr='P625').from_sparql_value(sparql_value).mainsnak.datavalue['value']['globe'] == 'http://example.org/globe>1'

    def test_earth_ranges(self):
        with pytest.raises(ValueError, match='latitude must be between -90 and 90'):
            GlobeCoordinate(latitude=120, longitude=2.5, prop_nr='P625')
        with pytest.raises(ValueError, match='longitude must be between -180 and 180'):
            GlobeCoordinate(latitude=1.5, longitude=200, prop_nr='P625')

    def test_other_globe_ranges(self):
        # Mars longitudes go from 0 to 360: Wikibase accepts -360 to 360 for both the latitude and the longitude
        coordinate = GlobeCoordinate(latitude=-1.9, longitude=354.5, globe='Q111', prop_nr='P625')

        assert coordinate.mainsnak.datavalue['value']['longitude'] == 354.5
        with pytest.raises(ValueError, match='longitude must be between -360 and 360'):
            GlobeCoordinate(latitude=-1.9, longitude=400, globe='Q111', prop_nr='P625')


class TestTime:
    def test_accessors(self):
        time = Time(time='-2023-12-31T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5')
        assert time.get_year() == -2023
        assert time.get_month() == 12
        assert time.get_day() == 31

    def test_comparisons(self):
        time = Time(time='-2023-12-31T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5')
        time2 = Time(time='2023-12-31T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5')

        assert time2.get_year() == 2023
        assert time == time
        assert time < time2
        assert time <= time2
        assert time != time2

    def test_large_year_parsing(self):
        # Years with more than 4 digits must be parsed correctly instead of being sliced at fixed positions
        time = Time(time='+10000-01-02T00:00:00Z', prop_nr='P5')
        assert time.get_year() == 10000
        assert time.get_month() == 1
        assert time.get_day() == 2

        # Ordering keeps working across the 4/5-digit boundary
        assert Time(time='+9999-01-01T00:00:00Z', prop_nr='P5') < time


class TestTimeRdfExport:
    """
    Time.sparql_time() gives the xsd:dateTime of the Wikibase RDF export (DateTimeValueCleaner and
    JulianDateTimeValueCleaner of Wikibase), Time.time_from_sparql() the timestamp of the JSON representation back.
    """

    @pytest.mark.parametrize('time, precision, calendarmodel, expected', [
        # The BCE years are numbered like in XSD 1.1, from the year precision: 44 BCE is the year -43, 1 BCE the year 0
        ('-0044-03-15T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '-0043-03-15T00:00:00Z'),
        ('-0100-00-00T00:00:00Z', WikibaseTimePrecision.YEAR, GREGORIAN_CALENDAR, '-0099-01-01T00:00:00Z'),
        ('-0001-05-00T00:00:00Z', WikibaseTimePrecision.MONTH, GREGORIAN_CALENDAR, '+0000-05-01T00:00:00Z'),
        ('-0500-00-00T00:00:00Z', WikibaseTimePrecision.CENTURY, GREGORIAN_CALENDAR, '-0500-01-01T00:00:00Z'),
        ('-13700000000-00-00T00:00:00Z', WikibaseTimePrecision.HUNDRED_MILLION_YEARS, GREGORIAN_CALENDAR, '-13700000000-01-01T00:00:00Z'),
        # A day of the Julian calendar is converted to the Gregorian calendar
        ('+1582-10-05T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '+1582-10-15T00:00:00Z'),
        ('+1500-03-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '+1500-03-11T00:00:00Z'),
        ('+1500-02-29T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '+1500-03-10T00:00:00Z'),
        ('-0044-03-15T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-0043-03-13T00:00:00Z'),
        # Below the day precision, a Julian date isn't converted
        ('+1500-03-00T00:00:00Z', WikibaseTimePrecision.MONTH, JULIAN_CALENDAR, '+1500-03-01T00:00:00Z'),
        ('-0044-00-00T00:00:00Z', WikibaseTimePrecision.YEAR, JULIAN_CALENDAR, '-0043-01-01T00:00:00Z'),
        # Out of the range of the calendar functions of PHP, a Julian date is exported as a Gregorian date
        ('-4713-01-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-4712-01-01T00:00:00Z'),
        ('-5000-03-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-4999-03-01T00:00:00Z'),
        # A day beyond the end of the month is the last day of the month
        ('+1987-02-30T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+1987-02-28T00:00:00Z'),
        ('+2000-02-31T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+2000-02-29T00:00:00Z'),
        ('+1987-04-31T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+1987-04-30T00:00:00Z'),
        ('-0005-02-29T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '-0004-02-29T00:00:00Z'),
        # Leading zeros of the year are dropped, the year keeps at least 4 digits
        ('+00001987-05-17T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+1987-05-17T00:00:00Z'),
        # Any other calendar model is read as the Gregorian calendar
        ('-0044-03-15T00:00:00Z', WikibaseTimePrecision.DAY, 'http://example.org/entity/Q1', '-0043-03-15T00:00:00Z'),
        # Without a precision nor a calendar model: a day of the Gregorian calendar
        ('-0044-03-15T00:00:00Z', None, None, '-0043-03-15T00:00:00Z'),
        # The year 0 doesn't exist in the JSON representation, Wikibase doesn't export it as an xsd:dateTime
        ('+0000-01-01T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+0000-01-01T00:00:00Z'),
    ])
    def test_sparql_time(self, time, precision, calendarmodel, expected):
        assert Time.sparql_time(time, precision, calendarmodel) == expected

    @pytest.mark.parametrize('time, precision, calendarmodel, expected', [
        ('-0043-03-15T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '-0044-03-15T00:00:00Z'),
        ('0000-01-01T00:00:00Z', WikibaseTimePrecision.YEAR, GREGORIAN_CALENDAR, '-0001-01-01T00:00:00Z'),
        ('-0500-01-01T00:00:00Z', WikibaseTimePrecision.CENTURY, GREGORIAN_CALENDAR, '-0500-01-01T00:00:00Z'),
        ('1987-05-17T00:00:00Z', WikibaseTimePrecision.DAY, GREGORIAN_CALENDAR, '+1987-05-17T00:00:00Z'),
        ('1582-10-15T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '+1582-10-05T00:00:00Z'),
        ('-0043-03-13T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-0044-03-15T00:00:00Z'),
        ('-0043-01-01T00:00:00Z', WikibaseTimePrecision.YEAR, JULIAN_CALENDAR, '-0044-01-01T00:00:00Z'),
        # 1 January 4713 BCE of the Julian calendar is exported as a Gregorian date, like 8 February
        ('-4712-01-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-4713-02-08T00:00:00Z'),
        ('-4999-03-01T00:00:00Z', WikibaseTimePrecision.DAY, JULIAN_CALENDAR, '-5000-03-01T00:00:00Z'),
        ('-0043-03-15T00:00:00Z', None, None, '-0044-03-15T00:00:00Z'),
    ])
    def test_time_from_sparql(self, time, precision, calendarmodel, expected):
        assert Time.time_from_sparql(time, precision, calendarmodel) == expected

    @pytest.mark.parametrize('time', ['2020', '+2020-01-01', ''])
    def test_time_from_sparql_not_a_timestamp(self, time):
        assert Time.time_from_sparql(time, WikibaseTimePrecision.YEAR) == time

    @pytest.mark.parametrize('calendarmodel', [GREGORIAN_CALENDAR, JULIAN_CALENDAR], ids=['gregorian', 'julian'])
    def test_round_trip(self, calendarmodel):
        """A timestamp exported then read back is the same timestamp, for the days that exist in its calendar."""
        for year, month, day, precision in itertools.product((-5000, -1000, -45, -44, -1, 1, 4, 1500, 1582, 1700, 2000, 2024, 1465072, 1465073),
                                                             range(1, 13), (1, 15, 28, 29, 30, 31), (7, 9, 10, 11)):
            astronomical_year = year + 1 if year < 0 else year
            if calendarmodel == JULIAN_CALENDAR and precision >= 11 and -4713 <= year <= 1465072:
                leap = astronomical_year % 4 == 0
            else:
                leap = astronomical_year % 4 == 0 and (astronomical_year % 100 != 0 or astronomical_year % 400 == 0)
            if day > ((29 if leap else 28) if month == 2 else 30 if month in (4, 6, 9, 11) else 31):
                continue
            if precision < 10:
                month = 1
            if precision < 11:
                day = 1
            time = f"{'-' if year < 0 else '+'}{abs(year):04d}-{month:02d}-{day:02d}T00:00:00Z"
            exported = Time.sparql_time(time, precision, calendarmodel)
            read_back = Time.time_from_sparql(exported.lstrip('+'), precision, calendarmodel)
            assert Time.sparql_time(read_back, precision, calendarmodel) == exported, (time, precision, exported)
            # Out of the range of the conversion, a Julian date can be exported like a Julian date of the range: the
            # years after 1465072 are exported unchanged, as the dates about 30 years before
            if year <= 1465072:
                assert read_back == time, (time, precision, exported)

    def test_from_sparql_value(self):
        # The simple value is a day of the Gregorian calendar, with the years numbered like in XSD 1.1
        time = Time(prop_nr='P1').from_sparql_value({'datatype': 'http://www.w3.org/2001/XMLSchema#dateTime', 'type': 'literal', 'value': '-0043-03-13T00:00:00Z'})
        assert time.mainsnak.datavalue['value']['time'] == '-0044-03-13T00:00:00Z'
        assert time.mainsnak.datavalue['value']['calendarmodel'] == GREGORIAN_CALENDAR
        assert time.get_sparql_value() == '"-0043-03-13T00:00:00Z"^^xsd:dateTime'

    def test_get_sparql_value_of_a_julian_date(self):
        time = Time(time='-0044-03-15T00:00:00Z', precision=WikibaseTimePrecision.DAY, calendarmodel=JULIAN_CALENDAR, prop_nr='P1')
        assert time.get_sparql_value() == '"-0043-03-13T00:00:00Z"^^xsd:dateTime'


class TestRank:
    def test_rank_parsing(self):
        t1 = String(value='test1', prop_nr='P1', rank='preferred')
        assert t1.rank == WikibaseRank.PREFERRED

        t2 = String(value='test1', prop_nr='P1', rank=WikibaseRank.NORMAL)
        assert t2.rank == WikibaseRank.NORMAL

        t3 = String(value='test1', prop_nr='P1', rank=WikibaseRank.DEPRECATED)
        assert t3.get_json()['rank'] == WikibaseRank.DEPRECATED.value

    def test_invalid_rank(self):
        with pytest.raises(ValueError):
            String(value='test1', prop_nr='P1', rank='invalid_rank')


class TestSnakType:
    def test_snaktype_parsing(self):
        t1 = String(value='test1', prop_nr='P1')
        t1.mainsnak.snaktype = 'novalue'
        assert t1.mainsnak.snaktype == WikibaseSnakType.NO_VALUE

        t2 = String(value='test1', prop_nr='P1')
        t2.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        assert t2.mainsnak.snaktype == WikibaseSnakType.UNKNOWN_VALUE

        t3 = String(value='test1', prop_nr='P1')
        t3.mainsnak.snaktype = WikibaseSnakType.KNOWN_VALUE
        assert t3.mainsnak.get_json()['snaktype'] == WikibaseSnakType.KNOWN_VALUE.value

    def test_invalid_snaktype(self):
        t4 = String(value='test1', prop_nr='P1')
        with pytest.raises(ValueError):
            t4.mainsnak.snaktype = 'invalid_value'

    def test_novalue_snak_has_no_datavalue(self):
        t5 = String(prop_nr='P1', snaktype=WikibaseSnakType.NO_VALUE)
        assert t5.mainsnak.get_json()['snaktype'] == WikibaseSnakType.NO_VALUE.value
        assert 'datavalue' not in t5.mainsnak.get_json()


class TestClaimCreation:
    """Ensure every datatype produces a valid claim JSON when added to a new item."""

    def test_all_datatypes(self):
        wbi = WikibaseIntegrator()
        data = [
            String(value='test1', prop_nr='P1'),
            String(value='test2', prop_nr='1'),
            String(value='test3', prop_nr=1),
            Math(value='xxx', prop_nr='P2'),
            ExternalID(value='xxx', prop_nr='P3'),
            Item(value='Q123', prop_nr='P4'),
            Item(value='123', prop_nr='P4'),
            Item(value=123, prop_nr='P4'),
            Item(value='Item:Q123', prop_nr='P4'),
            Item(value='http://www.wikidata.org/entity/Q123', prop_nr='P4'),
            Time(time='-0458-01-01T00:00:00Z', before=1, after=2, precision=WikibaseTimePrecision.MILLION_YEARS, timezone=4, prop_nr='P5'),
            Time(time='+458-01-01T00:00:00Z', before=1, after=2, precision=WikibaseTimePrecision.MILLION_YEARS, timezone=4, prop_nr='P5'),
            Time(time='+2021-01-01T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5'),
            Time(time='now', before=1, after=2, precision=WikibaseTimePrecision.MONTH, timezone=4, prop_nr='P5'),
            Time(time='+2021-01-00T00:00:00Z', before=1, after=2, precision=WikibaseTimePrecision.MONTH, timezone=4, prop_nr='P5'),
            Time(time='+2021-00-00T00:00:00Z', before=1, after=2, precision=WikibaseTimePrecision.YEAR, timezone=4, prop_nr='P5'),
            Time(time='+2021-00-00T00:00:00Z', before=1, after=2, precision=WikibaseTimePrecision.DECADE, timezone=4, prop_nr='P5'),
            Time(time='-13700000000-00-00T00:00:00Z', before=0, after=0, precision=WikibaseTimePrecision.HUNDRED_MILLION_YEARS, timezone=0, prop_nr='P585'),
            Time(time='-2450000000-00-00T00:00:00Z', before=0, after=0, precision=WikibaseTimePrecision.TEN_MILLION_YEARS, timezone=0, prop_nr='P585'),
            Time(time='-40000-00-00T00:00:00Z', before=0, after=0, precision=WikibaseTimePrecision.TEN_THOUSAND_YEARS, timezone=0, prop_nr='P585'),
            URL(value='http://www.wikidata.org', prop_nr='P6'),
            URL(value='https://www.wikidata.org', prop_nr='P6'),
            URL(value='ftp://example.com', prop_nr='P6'),
            URL(value='ssh://user@server/project.git', prop_nr='P6'),
            URL(value='svn+ssh://user@server:8888/path', prop_nr='P6'),
            MonolingualText(text='xxx', language='fr', prop_nr='P7'),
            Quantity(amount=-5.04, prop_nr='P8'),
            Quantity(amount=5.06, upper_bound=9.99, lower_bound=-2.22, unit='Q11573', prop_nr='P8'),
            CommonsMedia(value='xxx.jpg', prop_nr='P9'),
            GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr='P10'),
            GeoShape(value='Data:xxx.map', prop_nr='P11'),
            Property(value='P123', prop_nr='P12'),
            Property(value='123', prop_nr='P12'),
            Property(value=123, prop_nr='P12'),
            Property(value='Property:P123', prop_nr='P12'),
            Property(value='http://www.wikidata.org/entity/P123', prop_nr='P12'),
            TabularData(value='Data:Taipei+Population.tab', prop_nr='P13'),
            MusicalNotation(value="\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr='P14'),
            Lexeme(value='L123', prop_nr='P15'),
            Lexeme(value='123', prop_nr='P15'),
            Lexeme(value=123, prop_nr='P15'),
            Lexeme(value='Lexeme:L123', prop_nr='P15'),
            Lexeme(value='http://www.wikidata.org/entity/L123', prop_nr='P15'),
            Form(value='L123-F123', prop_nr='P16'),
            Sense(value='L123-S123', prop_nr='P17'),
        ]

        for claim in data:
            assert wbi.item.new().add_claims([claim]).get_json()
            assert wbi.item.new().add_claims(claim).get_json()

        assert wbi.item.new().add_claims(data).get_json()

    def test_extra_datatypes(self):
        wbi = WikibaseIntegrator()
        data = [
            EDTF(value='test1', prop_nr='P1'),
            LocalMedia(value='test2', prop_nr='P2'),
        ]

        for claim in data:
            assert wbi.item.new().add_claims([claim]).get_json()
            assert wbi.item.new().add_claims(claim).get_json()

        assert wbi.item.new().add_claims(data).get_json()


class TestDatatypeRegistry:
    def test_all_datatypes_registered_once(self):
        expected_datatypes = [
            'commonsMedia', 'entity-schema', 'external-id', 'wikibase-form', 'geo-shape', 'globe-coordinate', 'wikibase-item', 'wikibase-lexeme', 'math', 'monolingualtext',
            'musical-notation', 'wikibase-property', 'quantity', 'wikibase-sense', 'string', 'tabular-data', 'time', 'url',
            # Extra datatypes
            'edtf', 'localMedia',
        ]

        for dtype in expected_datatypes:
            assert len([x for x in BaseDataType.subclasses if x.DTYPE == dtype]) == 1, f'datatype {dtype} is not registered exactly once'

    def test_get_datatype_class(self):
        assert BaseDataType.get_datatype_class('wikibase-item') is Item
        assert BaseDataType.get_datatype_class(WikibaseDatatype.TIME) is Time
        assert BaseDataType.get_datatype_class('edtf') is EDTF

    def test_get_datatype_class_unknown(self):
        with pytest.raises(UnknownDatatypeError, match=r"Unknown datatype 'foo-type'\. Supported datatypes: .*wikibase-item") as excinfo:
            BaseDataType.get_datatype_class('foo-type')

        assert excinfo.value.datatype == 'foo-type'
        assert 'string' in excinfo.value.supported and excinfo.value.supported == sorted(excinfo.value.supported)
        # Callers catching a ValueError for a bad datatype keep working
        assert isinstance(excinfo.value, ValueError)


class TestLexemeSubIdentifiers:
    def test_get_lexeme_id(self):
        assert datatypes.Form(value='L123-F123', prop_nr='P16').get_lexeme_id() == 'L123'
        assert datatypes.Sense(value='L123-S123', prop_nr='P17').get_lexeme_id() == 'L123'


class TestFromSparqlValue:
    """
    from_sparql_value() rebuilds a claim from the RDF representation returned by a SPARQL endpoint. Fastrun compares
    the rebuilt claim with a local one through get_sparql_value(), so both must produce the very same value.
    """

    # (data type, SPARQL binding as returned by the endpoint, equivalent value of a local claim)
    round_trips = [
        (ExternalID, {'type': 'literal', 'value': '123-456'}, '123-456'),
        (MusicalNotation, {'type': 'literal', 'value': '\\relative c { e f }'}, '\\relative c { e f }'),
        (Property, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/P31'}, 'P31'),
        (EntitySchema, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/E10'}, 'E10'),
        (Lexeme, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/L5'}, 'L5'),
        (Form, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/L252248-F2'}, 'L252248-F2'),
        (Sense, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/L252248-S3'}, 'L252248-S3'),
        (GeoShape, {'type': 'uri', 'value': 'http://commons.wikimedia.org/data/main/Data:Paris.map'}, 'Data:Paris.map'),
        # The page title is percent-encoded in the URL and must be decoded to match the local claim
        (TabularData, {'type': 'uri', 'value': 'http://commons.wikimedia.org/data/main/Data:Taipei%20Population.tab'}, 'Data:Taipei Population.tab'),
        (CommonsMedia, {'type': 'uri', 'value': 'http://commons.wikimedia.org/wiki/Special:FilePath/Example%20file.jpg'}, 'Example file.jpg'),
    ]

    # (data type, SPARQL binding returned by the Wikidata Query Service, arguments of the equivalent local claim)
    attribute_round_trips: list[tuple[type[BaseDataType], dict, dict]] = [
        (Item, {'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q90'}, {'value': 'Q90'}),
        (String, {'type': 'literal', 'value': 'Paris'}, {'value': 'Paris'}),
        (URL, {'type': 'uri', 'value': 'https://www.paris.fr/'}, {'value': 'https://www.paris.fr/'}),
        (Quantity, {'datatype': 'http://www.w3.org/2001/XMLSchema#decimal', 'type': 'literal', 'value': '2175601'}, {'amount': 2175601}),
        (Time, {'datatype': 'http://www.w3.org/2001/XMLSchema#dateTime', 'type': 'literal', 'value': '1987-03-15T00:00:00Z'}, {'time': '+1987-03-15T00:00:00Z'}),
        (GlobeCoordinate, {'datatype': 'http://www.opengis.net/ont/geosparql#wktLiteral', 'type': 'literal', 'value': 'Point(2.352222222 48.856666666)'},
         {'latitude': 48.856666666, 'longitude': 2.352222222}),
        (MonolingualText, {'xml:lang': 'fr', 'type': 'literal', 'value': 'Paris'}, {'text': 'Paris', 'language': 'fr'}),
    ]

    @pytest.mark.parametrize('datatype,sparql_value,local_kwargs', attribute_round_trips, ids=[x[0].DTYPE for x in attribute_round_trips])
    def test_round_trip_with_attributes(self, datatype, sparql_value, local_kwargs):
        parsed = datatype(prop_nr='P1').from_sparql_value(sparql_value)

        assert parsed.get_sparql_value() == datatype(prop_nr='P1', **local_kwargs).get_sparql_value()

    def test_math_value_is_not_comparable(self):
        # The Wikidata Query Service returns the MathML rendering of c^2=a^2+b^2 (Q11518, P2534), not its TeX source
        mathml = {'datatype': 'http://www.w3.org/1998/Math/MathML', 'type': 'literal',
                  'value': '<math xmlns="http://www.w3.org/1998/Math/MathML"><msup><mi>c</mi><mn>2</mn></msup><mo>=</mo>...</math>'}

        with pytest.raises(ValueError, match="can't be compared through SPARQL"):
            Math(prop_nr='P1').from_sparql_value(mathml)

    @pytest.mark.parametrize('datatype,sparql_value,local_value', round_trips, ids=[x[0].DTYPE for x in round_trips])
    def test_round_trip(self, datatype, sparql_value, local_value):
        parsed = datatype(prop_nr='P1').from_sparql_value(sparql_value)

        assert parsed.get_sparql_value() == datatype(value=local_value, prop_nr='P1').get_sparql_value()

    # Values of Wikidata as returned by the Wikidata Query Service: CommonsMedia encodes the file name like PHP's
    # rawurlencode(), GeoShape and TabularData encode the page title like MediaWiki's wfUrlencode() (a space is a '+')
    commons_iris = [
        (CommonsMedia, 'Marie Curie (1900) (cropped).jpg', 'http://commons.wikimedia.org/wiki/Special:FilePath/Marie%20Curie%20%281900%29%20%28cropped%29.jpg'),
        (GeoShape, 'Data:Paris.map', 'http://commons.wikimedia.org/data/main/Data:Paris.map'),
        (GeoShape, 'Data:Protected areas/Germany/NI/Naturschutzgebiet Großes Meer, Loppersumer Meer.map',
         'http://commons.wikimedia.org/data/main/Data:Protected+areas/Germany/NI/Naturschutzgebiet+Gro%C3%9Fes+Meer,+Loppersumer+Meer.map'),
        (TabularData, 'Data:Population FR Q1657686.tab', 'http://commons.wikimedia.org/data/main/Data:Population+FR+Q1657686.tab'),
    ]

    @pytest.mark.parametrize('datatype,local_value,iri', commons_iris)
    def test_commons_values_use_the_rdf_iri(self, datatype, local_value, iri):
        # get_sparql_value() is written into the SPARQL queries: a relative IRI like <Data:Paris.map> never matched
        assert datatype(value=local_value, prop_nr='P1').get_sparql_value() == f'<{iri}>'
        assert datatype(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': iri}).mainsnak.datavalue['value'] == local_value

    # The unknown value ("some value" snak) of every data type, literal ones included, is a skolem IRI under the concept URI of
    # the instance, or a blank node on older query services
    unknown_values = [
        {'type': 'uri', 'value': 'http://www.wikidata.org/.well-known/genid/deadbeef'},
        {'type': 'uri', 'value': 'https://wikibase.example.org/.well-known/genid/deadbeef'},
        {'type': 'bnode', 'value': 't123'},
    ]

    @pytest.mark.parametrize('sparql_value', unknown_values, ids=['wikidata', 'other-wikibase', 'blank-node'])
    @pytest.mark.parametrize('datatype', BaseDataType.subclasses, ids=[x.DTYPE for x in BaseDataType.subclasses])
    def test_unknown_value(self, datatype, sparql_value):
        assert datatype(prop_nr='P1').from_sparql_value(sparql_value).mainsnak.snaktype == WikibaseSnakType.UNKNOWN_VALUE

    def test_wrong_type_is_rejected(self):
        # An entity is always a URI, a literal must not be silently accepted
        with pytest.raises(ValueError, match='Wrong SPARQL type'):
            Property(prop_nr='P1').from_sparql_value({'type': 'literal', 'value': 'P31'})

        # ExternalID is the other way around
        with pytest.raises(ValueError, match='Wrong SPARQL type'):
            ExternalID(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://example.org/123'})

    def test_unparsable_value_is_rejected(self):
        # The callers rely on a ValueError to skip the values they can't compare, rather than storing a wrong one
        with pytest.raises(ValueError, match='Invalid SPARQL value'):
            Form(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://www.wikidata.org/entity/L252248'})

        with pytest.raises(ValueError, match='Invalid SPARQL value'):
            GeoShape(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://commons.wikimedia.org/data/main/Data:Paris.tab'})

        with pytest.raises(ValueError, match='Invalid SPARQL value'):
            EntitySchema(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'http://www.wikidata.org/entity/Q10'})

    def test_property_types(self):
        # The property types of the Wikibase ontology, as returned by wikibase:propertyType on Wikidata. Fastrun finds
        # the data type of a loaded value from them: a wrong one makes the value never match.
        assert Property.PTYPE == 'http://wikiba.se/ontology#WikibaseProperty'
        assert EntitySchema.PTYPE == 'http://wikiba.se/ontology#WikibaseEntitySchema'

    def test_property_types_of_the_extensions(self):
        # Wikibase builds the URI from the data type ID of the extension: they used to inherit the type of String
        assert EDTF.PTYPE == 'http://wikiba.se/ontology#Edtf'
        assert LocalMedia.PTYPE == 'http://wikiba.se/ontology#LocalMedia'


class TestExtraDataTypesSparql:
    def test_edtf_literal(self):
        edtf = EDTF(prop_nr='P1').from_sparql_value({'datatype': 'http://www.w3.org/2001/XMLSchema#edtf', 'type': 'literal', 'value': '1985-04-12/..'})

        assert edtf.mainsnak.datavalue['value'] == '1985-04-12/..'

    def test_edtf_covered_dates_are_not_the_value(self):
        # The extension also writes the dates covered by the EDTF value, as xsd:dateTime values of the same statement
        with pytest.raises(ValueError, match='Not the EDTF literal'):
            EDTF(prop_nr='P1').from_sparql_value({'datatype': 'http://www.w3.org/2001/XMLSchema#dateTime', 'type': 'literal', 'value': '1985-04-12T00:00:00Z'})

    @pytest.mark.parametrize('url,file_name', [
        ('https://wiki.example.org/wiki/File:Bunny.jpg', 'Bunny.jpg'),
        ('https://wiki.example.org/wiki/File:Bunny_rabbit_%28white%29.jpg', 'Bunny rabbit (white).jpg'),
        ('https://wiki.example.org/w/index.php?title=File:Bunny_rabbit.jpg', 'Bunny rabbit.jpg'),
        ('https://wiki.example.org/wiki/Fichier:Lapin.jpg', 'Lapin.jpg'),  # a localized namespace
        ('https://wiki.example.org/wiki/File:Map:2024.png', 'Map:2024.png'),
    ])
    def test_local_media_file_page_url(self, url, file_name):
        local_media = LocalMedia(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': url})

        assert local_media.mainsnak.datavalue['value'] == file_name
        assert local_media.get_sparql_value() == LocalMedia(value=file_name, prop_nr='P1').get_sparql_value()

    def test_local_media_not_a_file_page(self):
        with pytest.raises(ValueError, match='Not the URL of a file page'):
            LocalMedia(prop_nr='P1').from_sparql_value({'type': 'uri', 'value': 'https://wiki.example.org/wiki/Bunny'})
        with pytest.raises(ValueError, match='Wrong SPARQL type'):
            LocalMedia(prop_nr='P1').from_sparql_value({'type': 'literal', 'value': 'Bunny.jpg'})
