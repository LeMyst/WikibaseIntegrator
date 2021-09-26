from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config


class GlobeCoordinate(BaseDataType):
    """
    Implements the Wikibase data type for globe coordinates
    """
    DTYPE = 'globe-coordinate'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^geo:wktLiteral .
        }}
    '''

    def __init__(self, latitude: float = None, longitude: float = None, precision: float = None, globe: str = None, wikibase_url: str = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param latitude: Latitute in decimal format
        :param longitude: Longitude in decimal format
        :param precision: Precision of the position measurement, default 1 / 3600
        :param globe: The globe entity concept URI (ex: http://www.wikidata.org/entity/Q2) or 'Q2'
        :param wikibase_url: The default wikibase URL, used when the globe is only an ID like 'Q2'. Use wbi_config['WIKIBASE_URL'] by default.
        """

        super().__init__(**kwargs)

        # https://github.com/wikimedia/Wikibase/blob/174450de8fdeabcf97287604dbbf04d07bb5000c/repo/includes/Rdf/Values/GlobeCoordinateRdfBuilder.php#L120
        precision = precision or 1 / 3600
        globe = globe or str(config['COORDINATE_GLOBE_QID'])
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        # TODO: Introduce validity checks for coordinates, etc.
        # TODO: Add check if latitude/longitude/precision is None

        if latitude and longitude:
            if latitude < -90 or latitude > 90:
                raise ValueError(f"latitude must be between -90 and 90, got '{latitude}'")
            if longitude < -180 or longitude > 180:
                raise ValueError(f"longitude must be between -180 and 180, got '{longitude}'")

            self.mainsnak.datavalue = {
                'value': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'precision': precision,
                    'globe': globe
                },
                'type': 'globecoordinate'
            }

    def _get_sparql_value(self) -> str:
        return 'Point(' + str(self.mainsnak.datavalue['value']['latitude']) + ', ' + str(self.mainsnak.datavalue['value']['longitude']) + ')'
