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

    def __init__(self, latitude=None, longitude=None, precision=None, globe=None, wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param latitude: Latitute in decimal format
        :type latitude: float or None
        :param longitude: Longitude in decimal format
        :type longitude: float or None
        :param precision: Precision of the position measurement
        :type precision: float or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super().__init__(**kwargs)

        globe = globe or config['COORDINATE_GLOBE_QID']
        wikibase_url = wikibase_url or config['WIKIBASE_URL']

        self.latitude = None
        self.longitude = None
        self.precision = None
        self.globe = None

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        # TODO: Introduce validity checks for coordinates, etc.
        # TODO: Add check if latitude/longitude/precision is None
        self.latitude = latitude
        self.longitude = longitude
        self.precision = precision
        self.globe = globe

        if self.latitude and self.longitude and self.precision:
            self.value = (self.latitude, self.longitude, self.precision, self.globe)
        else:
            self.value = None

        if self.value:
            self.mainsnak.datavalue = {
                'value': {
                    'latitude': self.latitude,
                    'longitude': self.longitude,
                    'precision': self.precision,
                    'globe': self.globe
                },
                'type': 'globecoordinate'
            }

    def get_sparql_value(self):
        return 'Point(' + str(self.latitude) + ', ' + str(self.longitude) + ')'
