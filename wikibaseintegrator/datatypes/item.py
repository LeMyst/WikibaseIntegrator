import re
from typing import Any, Union

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class Item(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-item' with a value being another item ID
    """
    DTYPE = 'wikibase-item'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value: Union[str, int] = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The item ID to serve as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: Union[str, int] = None):
        assert isinstance(value, (str, int)) or value is None, f'Expected str or int, found {type(value)} ({value})'

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^Q?([0-9]+)$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError(f"Invalid item ID ({value}), format must be 'Q[0-9]+'")

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'item',
                    'numeric-id': value,
                    'id': f'Q{value}'
                },
                'type': 'wikibase-entityid'
            }

    def get_sparql_value(self) -> str:
        return '<{wb_url}/entity/' + self.mainsnak.datavalue['value']['id'] + '>'
