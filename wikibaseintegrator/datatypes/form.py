import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_jsonparser import JsonParser


class Form(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-form'
    """
    DTYPE = 'wikibase-form'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The form number to serve as a value using the format "L<Lexeme ID>-F<Form ID>" (example: L252248-F2)
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

        super(Form, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            pattern = re.compile(r'^L[0-9]+-F[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid form ID ({}), format must be 'L[0-9]+-F[0-9]+'".format(value))

            self.value = value

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'form',
                'id': self.value
            },
            'type': 'wikibase-entityid'
        }

        super(Form, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['id'], prop_nr=jsn['property'])
