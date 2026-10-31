from __future__ import annotations

from typing import Self

from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class EDTF(String):
    """
    Implements the Wikibase data type for Wikibase Extended Date/Time Format extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF
    """
    DTYPE = WikibaseDatatype.EDTF
    # Wikibase builds the URI from the data type ID ('edtf'), the extension doesn't set one
    PTYPE = 'http://wikiba.se/ontology#Edtf'
    #: The datatype of the EDTF literal in the RDF export
    XSD_EDTF = 'http://www.w3.org/2001/XMLSchema#edtf'

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        The extension writes the EDTF string as an xsd:edtf literal, then the dates it covers as xsd:dateTime values of the
        same statement: only the EDTF literal is the value of the claim.

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: The object itself
        """
        if not self._is_unknown_value(sparql_value) and sparql_value.get('datatype', self.XSD_EDTF) != self.XSD_EDTF:
            raise ValueError(f"Not the EDTF literal of the statement, but one of the dates it covers ({sparql_value.get('datatype')})")

        return super().from_sparql_value(sparql_value)
