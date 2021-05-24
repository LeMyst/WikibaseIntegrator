import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_jsonparser import JsonParser


class GeoShape(BaseDataType):
    """
    Implements the Wikibase data type 'geo-shape'
    """
    DTYPE = 'geo-shape'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The GeoShape map file name in Wikimedia Commons to be linked
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(GeoShape, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Paris.map
            pattern = re.compile(r'^Data:((?![:|#]).)+\.map$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .map. In addition title should not contain characters like colon, hash or pipe.")
            self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(GeoShape, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])
