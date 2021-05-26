import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_jsonparser import JsonParser


class Sense(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-sense'
    """
    DTYPE = 'wikibase-sense'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Value using the format "L<Lexeme ID>-S<Sense ID>" (example: L252248-S123)
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Sense, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            pattern = re.compile(r'^L[0-9]+-S[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid sense ID ({}), format must be 'L[0-9]+-S[0-9]+'".format(value))

            self.value = value

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'sense',
                'id': self.value
            },
            'type': 'wikibase-entityid'
        }

        super(Sense, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snaktype=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['id'], prop_nr=jsn['property'])
