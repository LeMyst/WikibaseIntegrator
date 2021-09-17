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
        :param precision: Precision of the position measurement, default 1 / 3600
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

        precision = precision or 1 / 3600  # https://github.com/wikimedia/Wikibase/blob/174450de8fdeabcf97287604dbbf04d07bb5000c/repo/includes/Rdf/Values/GlobeCoordinateRdfBuilder.php#L120
        globe = globe or config['COORDINATE_GLOBE_QID']
        wikibase_url = wikibase_url or config['WIKIBASE_URL']

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        # TODO: Introduce validity checks for coordinates, etc.
        # TODO: Add check if latitude/longitude/precision is None

        if latitude and longitude:
            if latitude < -90 or latitude > 90:
                raise ValueError("latitude must be between -90 and 90, got '{}'".format(latitude))
            if longitude < -180 or longitude > 180:
                raise ValueError("longitude must be between -180 and 180, got '{}'".format(longitude))

            self.mainsnak.datavalue = {
                'value': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'precision': precision,
                    'globe': globe
                },
                'type': 'globecoordinate'
            }

    def get_sparql_value(self):
        return 'Point(' + str(self.mainsnak.datavalue['value']['latitude']) + ', ' + str(self.mainsnak.datavalue['value']['longitude']) + ')'
