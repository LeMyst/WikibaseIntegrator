from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType

#: The globe Wikibase omits from the WKT literal of a coordinate (GlobeCoordinateValue::GLOBE_EARTH), on every Wikibase instance
GLOBE_EARTH = 'http://www.wikidata.org/entity/Q2'


def _wdqs_number(value: float) -> str:
    """
    A latitude or a longitude as the Wikidata Query Service returns it in a WKT literal.

    Wikibase writes it with 14 significant digits (the PHP float format), the query service stores it as a fixed-point
    number with 9 decimals, truncated (the multiplier 1000000000 of its geospatial configuration), and returns that number
    formatted by Java's Double.toString(): 2.352222222222222 -> '2.352222222', 47 -> '47.0', 0.0005 -> '5.0E-4'.
    """
    stored = math.trunc(float(f'{value:.14G}') * 1_000_000_000) / 1_000_000_000
    if stored == 0:
        return '0.0'
    if 1e-3 <= abs(stored) < 1e7:
        # Like Java, the shortest decimal representation, with at least one decimal
        return repr(stored)
    # Java switches to the computerized scientific notation below 10^-3
    sign, digits, exponent = Decimal(repr(stored)).as_tuple()
    assert isinstance(exponent, int)
    mantissa = f"{digits[0]}.{''.join(map(str, digits[1:])) or '0'}"
    return f"{'-' if sign else ''}{mantissa}E{len(digits) - 1 + exponent}"


class GlobeCoordinate(BaseDataType):
    """
    Implements the Wikibase data type for globe coordinates
    """
    DTYPE = WikibaseDatatype.GLOBECOORDINATE
    PTYPE = 'http://wikiba.se/ontology#GlobeCoordinate'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^geo:wktLiteral .
        }}
    '''

    def __init__(self, latitude: float | None = None, longitude: float | None = None, altitude: float | None = None, precision: float | None = None, globe: str | None = None, wikibase_url: str | None = None,
                 **kwargs: Any) -> None:
        """
        Constructor, calls the superclass BaseDataType

        :param latitude: Latitude in decimal format, between -90 and 90 on Earth, -360 and 360 on another globe (like Wikibase)
        :param longitude: Longitude in decimal format, between -180 and 180 on Earth, -360 and 360 on another globe (like Wikibase)
        :param altitude: Altitude (in decimal format?) (Always None at this moment)
        :param precision: Precision of the position measurement, default 1 / 3600
        :param globe: The globe entity concept URI (ex: http://www.wikidata.org/entity/Q2) or 'Q2'
        :param wikibase_url: The default wikibase URL, used when the globe is only an ID like 'Q2'. Use wbi_config['WIKIBASE_URL'] by default.
        """

        super().__init__(**kwargs)
        self.set_value(latitude=latitude, longitude=longitude, altitude=altitude, precision=precision, globe=globe, wikibase_url=wikibase_url)

    # The keyword arguments of this public method are named after the parts of the value, not 'value' like in BaseDataType
    # pylint: disable-next=arguments-renamed
    def set_value(self, latitude: float | None = None, longitude: float | None = None, altitude: float | None = None, precision: float | None = None, globe: str | None = None, wikibase_url: str | None = None) -> None:
        # https://github.com/wikimedia/Wikibase/blob/174450de8fdeabcf97287604dbbf04d07bb5000c/repo/includes/Rdf/Values/GlobeCoordinateRdfBuilder.php#L120
        precision = precision or 1 / 3600
        globe = globe or str(config['COORDINATE_GLOBE_QID'])
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        if latitude is not None and longitude is not None:
            # Wikibase accepts -360 to 360 for both, which the coordinates of other globes use (e.g. Mars longitudes go from 0
            # to 360). On Earth, the geographic ranges are kept, catching a latitude and a longitude swapped.
            if globe in (GLOBE_EARTH, str(config['COORDINATE_GLOBE_QID'])):
                max_latitude, max_longitude = 90, 180
            else:
                max_latitude, max_longitude = 360, 360
            if latitude < -max_latitude or latitude > max_latitude:
                raise ValueError(f"latitude must be between -{max_latitude} and {max_latitude}, got '{latitude}'")
            if longitude < -max_longitude or longitude > max_longitude:
                raise ValueError(f"longitude must be between -{max_longitude} and {max_longitude}, got '{longitude}'")

            self.mainsnak.datavalue = {
                'value': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'altitude': altitude,
                    'precision': precision,
                    'globe': globe
                },
                'type': 'globecoordinate'
            }

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Claim) and self.mainsnak.datavalue.get('type') == 'globecoordinate' and other.mainsnak.datavalue.get('type') == 'globecoordinate':
            # Compare rounded copies to ignore precision noise without mutating the claims
            def rounded(datavalue: dict) -> dict:
                value = dict(datavalue['value'])
                value['latitude'] = round(value['latitude'], 6)
                value['longitude'] = round(value['longitude'], 6)
                # The precision can be null in the JSON of Wikibase, e.g. old coordinates of Wikidata
                if value.get('precision') is not None:
                    value['precision'] = round(value['precision'], 17)
                return {**datavalue, 'value': value}

            return rounded(self.mainsnak.datavalue) == rounded(other.mainsnak.datavalue) and self.mainsnak.property_number == other.mainsnak.property_number \
                and self.has_equal_qualifiers(other)

        return super().__eq__(other)

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: True if the parsing is successful
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.opengis.net/ont/geosparql#wktLiteral':
            raise ValueError('Wrong SPARQL datatype')

        if type != 'literal':
            raise ValueError('Wrong SPARQL type')

        # The globe prefixes the point, except Earth: '<http://www.wikidata.org/entity/Q111> Point(354.5 -1.9)' (Mars)
        pattern = re.compile(r'^(?:<([^>]*)> )?Point\((\S+) (\S+)\)$')
        matches = pattern.match(value)
        if not matches:
            raise ValueError('Invalid SPARQL value')

        # Wikibase writes a '>' of the globe IRI as '%3E'
        globe = matches.group(1).replace('%3E', '>') if matches.group(1) else GLOBE_EARTH
        self.set_value(longitude=float(matches.group(2)), latitude=float(matches.group(3)), globe=globe)

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        """
        The WKT literal of the coordinate, in the form returned by the Wikidata Query Service: the globe prefixes the point
        when it isn't Earth, and the numbers are truncated to 9 decimals. The query service normalizes the literals of a
        query the same way, so the literal matches the stored value, and the values loaded by the fast run mode are
        indexed by the same string as the local claims.
        """
        value = self.mainsnak.datavalue['value']
        point = f"Point({_wdqs_number(value['longitude'])} {_wdqs_number(value['latitude'])})"
        globe = value.get('globe') or GLOBE_EARTH
        if globe != GLOBE_EARTH:
            point = f"<{globe.replace('>', '%3E')}> {point}"
        return f'"{point}"^^geo:wktLiteral'

    def parse_sparql_value(self, value: str, type: str = 'literal', unit: str = '1') -> bool:
        pattern = re.compile(r'^"?Point\((.*) (.*)\)"?(?:\^\^geo:wktLiteral)?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(longitude=float(matches.group(1)), latitude=float(matches.group(2)))
        return True
