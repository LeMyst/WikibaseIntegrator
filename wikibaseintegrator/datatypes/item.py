from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class Item(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-item' with a value being another item ID
    """
    DTYPE = 'wikibase-item'
    PTYPE = 'http://wikiba.se/ontology#WikibaseItem'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value: str | int | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The item ID to serve as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | int | None = None):
        assert isinstance(value, (str, int)) or value is None, f'Expected str or int, found {type(value)} ({value})'

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^(?:[a-zA-Z]+:|.+\/entity\/)?Q?([0-9]+)$')
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

    def from_sparql_value(self, sparql_value: dict) -> Item:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return: True if the parsing is successful
        """
        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'uri':
            raise ValueError('Wrong SPARQL type')

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            pattern = re.compile(r'^.+/([PQLM]\d+)$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError(f"Invalid SPARQL value {value}")

            self.set_value(value=str(matches.group(1)))

        return self

    def get_sparql_value(self, **kwargs: Any) -> str | None:
        if self.mainsnak.snaktype == WikibaseSnakType.KNOWN_VALUE:
            wikibase_url = str(kwargs['wikibase_url'] if 'wikibase_url' in kwargs else config['WIKIBASE_URL'])
            return f'<{wikibase_url}/entity/' + self.mainsnak.datavalue['value']['id'] + '>'

        return None
