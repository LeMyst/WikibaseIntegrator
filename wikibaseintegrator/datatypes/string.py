from __future__ import annotations

from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class String(BaseDataType):
    """
    Implements the Wikibase data type 'string'
    """
    DTYPE = 'string'
    PTYPE = 'http://wikiba.se/ontology#String'

    def __init__(self, value: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The string to be used as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value and ('\n' in value or '\r' in value):
            raise ValueError("String value must not contain new ine character")

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }

    def from_sparql_value(self, sparql_value: dict) -> String:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'literal':
            raise ValueError(f"Wrong SPARQL type {type}")

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            self.set_value(value=value)

        return self
