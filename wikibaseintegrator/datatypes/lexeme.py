import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_jsonparser import JsonParser


class Lexeme(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-lexeme'
    """
    DTYPE = 'wikibase-lexeme'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/L{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The lexeme number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
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

        super(Lexeme, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, (str, int)) or value is None, "Expected str or int, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^L?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid lexeme ID ({}), format must be 'L[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'lexeme',
                'numeric-id': self.value,
                'id': 'L{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }

        super(Lexeme, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['numeric-id'], prop_nr=jsn['property'])
