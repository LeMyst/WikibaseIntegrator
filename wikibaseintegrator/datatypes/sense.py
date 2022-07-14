import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


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

    def __init__(self, value: str = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: Value using the format "L<Lexeme ID>-S<Sense ID>" (example: L252248-S123)
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            pattern = re.compile(r'^L[0-9]+-S[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid sense ID ({value}), format must be 'L[0-9]+-S[0-9]+'")

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'sense',
                    'id': value
                },
                'type': 'wikibase-entityid'
            }

    def get_sparql_value(self) -> str:
        return self.mainsnak.datavalue['value']['id']
