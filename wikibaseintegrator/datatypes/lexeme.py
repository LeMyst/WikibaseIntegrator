import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


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

    def __init__(self, value=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The lexeme number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
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

        super(Lexeme, self).__init__(**kwargs)

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

        if self.value:
            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'lexeme',
                    'numeric-id': self.value,
                    'id': 'L{}'.format(self.value)
                },
                'type': 'wikibase-entityid'
            }
