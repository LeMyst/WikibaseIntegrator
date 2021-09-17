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
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value: str = None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The lexeme number to serve as a value
        """

        super().__init__(**kwargs)

        assert isinstance(value, (str, int)) or value is None, "Expected str or int, found {} ({})".format(type(value), value)

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^L?([0-9]+)$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError("Invalid lexeme ID ({}), format must be 'L[0-9]+'".format(value))

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'lexeme',
                    'numeric-id': value,
                    'id': 'L{}'.format(value)
                },
                'type': 'wikibase-entityid'
            }

    def get_sparql_value(self):
        return self.mainsnak.datavalue['value']['id']
