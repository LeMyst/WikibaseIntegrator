from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_jsonparser import JsonParser


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

    def __init__(self, latitude, longitude, precision, globe=None, wikibase_url=None, **kwargs):
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

        globe = globe or config['COORDINATE_GLOBE_QID']
        wikibase_url = wikibase_url or config['WIKIBASE_URL']

        self.latitude = None
        self.longitude = None
        self.precision = None
        self.globe = None

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        value = (latitude, longitude, precision, globe)

        super(GlobeCoordinate, self).__init__(value=value, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        # TODO: Introduce validity checks for coordinates, etc.
        # TODO: Add check if latitude/longitude/precision is None
        self.latitude, self.longitude, self.precision, self.globe = value

        self.mainsnak.datavalue = {
            'value': {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'precision': self.precision,
                'globe': self.globe
            },
            'type': 'globecoordinate'
        }

        self.value = (self.latitude, self.longitude, self.precision, self.globe)
    def get_sparql_value(self):
        return 'Point(' + str(self.latitude) + ', ' + str(self.longitude) + ')'

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(latitude=None, longitude=None, precision=None, prop_nr=jsn['property'],
                       snaktype=jsn['snaktype'])

        value = jsn['datavalue']['value']
        return cls(latitude=value['latitude'], longitude=value['longitude'], precision=value['precision'],
                   prop_nr=jsn['property'])
