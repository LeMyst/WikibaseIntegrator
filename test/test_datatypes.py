"""
Serialization tests for the datatypes: they validate that the JSON produced
locally by the library matches what a Wikibase instance expects. No network
interaction is involved.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import (URL, BaseDataType, CommonsMedia, ExternalID, Form, GeoShape, GlobeCoordinate, Item, Lexeme, Math, MonolingualText, MusicalNotation,
                                          Property, Quantity, Sense, String, TabularData, Time)
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseRank, WikibaseSnakType, WikibaseTimePrecision


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
            CommonsMedia(value='xxx', prop_nr='P9'),
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


class TestLexemeSubIdentifiers:
    def test_get_lexeme_id(self):
        assert datatypes.Form(value='L123-F123', prop_nr='P16').get_lexeme_id() == 'L123'
        assert datatypes.Sense(value='L123-S123', prop_nr='P17').get_lexeme_id() == 'L123'
