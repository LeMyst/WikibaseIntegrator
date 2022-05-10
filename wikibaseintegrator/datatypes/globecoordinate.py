from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.models import Claim
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class GlobeCoordinate(BaseDataType):
    """
    Implements the Wikibase data type for globe coordinates
    """
    DTYPE = 'globe-coordinate'
    PTYPE = 'http://wikiba.se/ontology#GlobeCoordinate'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^geo:wktLiteral .
        }}
    '''

    def __init__(self, latitude: float | None = None, longitude: float | None = None, altitude: float | None = None, precision: float | None = None, globe: str | None = None, wikibase_url: str | None = None,
                 **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param latitude: Latitude in decimal format
        :param longitude: Longitude in decimal format
        :param altitude: Altitude (in decimal format?) (Always None at this moment)
        :param precision: Precision of the position measurement, default 1 / 3600
        :param globe: The globe entity concept URI (ex: http://www.wikidata.org/entity/Q2) or 'Q2'
        :param wikibase_url: The default wikibase URL, used when the globe is only an ID like 'Q2'. Use wbi_config['WIKIBASE_URL'] by default.
        """

        super().__init__(**kwargs)
        self.set_value(latitude=latitude, longitude=longitude, altitude=altitude, precision=precision, globe=globe, wikibase_url=wikibase_url)

    def set_value(self, latitude: float | None = None, longitude: float | None = None, altitude: float | None = None, precision: float | None = None, globe: str | None = None, wikibase_url: str | None = None):
        # https://github.com/wikimedia/Wikibase/blob/174450de8fdeabcf97287604dbbf04d07bb5000c/repo/includes/Rdf/Values/GlobeCoordinateRdfBuilder.php#L120
        precision = precision or 1 / 3600
        globe = globe or str(config['COORDINATE_GLOBE_QID'])
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        if latitude is not None and longitude is not None:
            if latitude < -90 or latitude > 90:
                raise ValueError(f"latitude must be between -90 and 90, got '{latitude}'")
            if longitude < -180 or longitude > 180:
                raise ValueError(f"longitude must be between -180 and 180, got '{longitude}'")

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

    def __eq__(self, other):
        if isinstance(other, Claim) and other.mainsnak.datavalue['type'] == 'globecoordinate':
            tmp_datavalue_self = self.mainsnak.datavalue
            tmp_datavalue_other = other.mainsnak.datavalue

            tmp_datavalue_self['value']['latitude'] = round(tmp_datavalue_self['value']['latitude'], 6)
            tmp_datavalue_self['value']['longitude'] = round(tmp_datavalue_self['value']['longitude'], 6)
            tmp_datavalue_self['value']['precision'] = round(tmp_datavalue_self['value']['precision'], 17)

            tmp_datavalue_other['value']['latitude'] = round(tmp_datavalue_other['value']['latitude'], 6)
            tmp_datavalue_other['value']['longitude'] = round(tmp_datavalue_other['value']['longitude'], 6)
            tmp_datavalue_other['value']['precision'] = round(tmp_datavalue_other['value']['precision'], 17)

            return tmp_datavalue_self == tmp_datavalue_other and self.mainsnak.property_number == other.mainsnak.property_number and self.has_equal_qualifiers(other)

        return super().__eq__(other)

    def from_sparql_value(self, sparql_value: dict) -> GlobeCoordinate:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: True if the parsing is successful
        """
        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.opengis.net/ont/geosparql#wktLiteral':
            raise ValueError('Wrong SPARQL datatype')

        if type != 'literal':
            raise ValueError('Wrong SPARQL type')

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            pattern = re.compile(r'^Point\((.*) (.*)\)$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError('Invalid SPARQL value')

            self.set_value(longitude=float(matches.group(1)), latitude=float(matches.group(2)))

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        return '"Point(' + str(self.mainsnak.datavalue['value']['longitude']) + ' ' + str(self.mainsnak.datavalue['value']['latitude']) + ')"^^geo:wktLiteral'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^"?Point\((.*) (.*)\)"?(?:\^\^geo:wktLiteral)?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(longitude=float(matches.group(1)), latitude=float(matches.group(2)))
        return True
