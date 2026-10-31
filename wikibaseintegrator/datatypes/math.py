from __future__ import annotations

from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import sparql_string
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

        Only an unknown value can be parsed: the RDF export holds a formula rendered as MathML (e.g. <math ...><msup><mi>c</mi>...),
        not its TeX source, which is the value of the claim (c^2=a^2+b^2). The two can't be compared, so a known value raises a
        ValueError and is left out of the fast run data.

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        datatype = sparql_value.get('datatype')
        if datatype != 'http://www.w3.org/1998/Math/MathML':
            raise ValueError(f"Wrong SPARQL datatype {datatype}")

        raise ValueError("A Math value can't be compared through SPARQL: the RDF export holds its MathML rendering, not its TeX source")

    def get_sparql_value(self, **kwargs: Any) -> str:
        return sparql_string(self.mainsnak.datavalue['value']) + '^^<http://www.w3.org/1998/Math/MathML>'
