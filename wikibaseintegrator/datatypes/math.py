from __future__ import annotations

from typing import Any, Self

from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class Math(String):
    """
    Implements the Wikibase data type 'math' for mathematical formula in TEX format
    """
    DTYPE = WikibaseDatatype.MATH
    PTYPE = 'http://wikiba.se/ontology#Math'

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.w3.org/2001/XMLSchema#dateTime':
            raise ValueError('Wrong SPARQL datatype')

        if type != 'literal':
            raise ValueError('Wrong SPARQL type')

        self.set_value(value=value)

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        return '"' + self.mainsnak.datavalue['value'] + '"^^<http://www.w3.org/1998/Math/MathML>'
