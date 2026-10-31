"""
Serialization tests for the datatypes: they validate that the JSON produced
locally by the library matches what a Wikibase instance expects. No network
interaction is involved.
"""
import pytest

from wikibaseintegrator import WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import (URL, BaseDataType, CommonsMedia, EntitySchema, ExternalID, Form, GeoShape, GlobeCoordinate, Item, Lexeme, Math, MonolingualText,
                                          MusicalNotation, Property, Quantity, Sense, String, TabularData, Time)
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
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
