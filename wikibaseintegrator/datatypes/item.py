import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_jsonparser import JsonParser


class Item(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-item' with a value being another item ID
    """
    DTYPE = 'wikibase-item'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/Q{value}> .
        }}
    '''

    def __init__(self, value, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The item ID to serve as the value
        :type value: str with a 'Q' prefix, followed by several digits or only the digits without the 'Q' prefix
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

        super(Item, self).__init__(value=value, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, (str, int)) or value is None, 'Expected str or int, found {} ({})'.format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^Q?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid item ID ({}), format must be 'Q[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.mainsnak.datavalue = {
            'value': {
                'entity-type': 'item',
                'numeric-id': self.value,
                'id': 'Q{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snaktype=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['numeric-id'], prop_nr=jsn['property'])
