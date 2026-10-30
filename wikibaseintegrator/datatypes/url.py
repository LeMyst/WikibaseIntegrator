from __future__ import annotations

import re
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class URL(BaseDataType):
    """
    Implements the Wikibase data type for URL strings
    """
    DTYPE = WikibaseDatatype.URL
    PTYPE = 'http://wikiba.se/ontology#Url'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The URL to be used as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            pattern = re.compile(r'^([a-z][a-z\d+.-]*):([^][<>\"\x00-\x20\x7F])+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid URL {value}")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'uri':
            raise ValueError(f"Wrong SPARQL type {type}")

        self.set_value(value=value)
        return self

    def get_sparql_value(self, **kwargs: Any) -> str | None:
        if self.mainsnak.snaktype != WikibaseSnakType.KNOWN_VALUE:
            return None
        return '<' + self.mainsnak.datavalue['value'] + '>'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^<?(.*?)>?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(value=matches.group(1))

        return True
