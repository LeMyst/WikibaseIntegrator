from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class Property(BaseDataType):
    """
    Implements the Wikibase data type 'property'
    """
    DTYPE = 'wikibase-property'
    PTYPE = 'http://wikiba.se/ontology#Property'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/P{value}> .
        }}
    '''

    def __init__(self, value: str | int | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The property number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | int | None = None):
        assert isinstance(value, (str, int)) or value is None, f"Expected str or int, found {type(value)} ({value})"

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^(?:[a-zA-Z]+:|.+\/entity\/)?P?([0-9]+)$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError(f"Invalid property ID ({value}), format must be 'P[0-9]+'")

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'property',
                    'numeric-id': value,
                    'id': f'P{value}'
                },
                'type': 'wikibase-entityid'
            }

    def from_sparql_value(self, sparql_value: dict) -> Property:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'uri':
            raise ValueError(f"Wrong SPARQL type {type}")

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            pattern = re.compile(r'^.+/(P[0-9]+)$')
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
