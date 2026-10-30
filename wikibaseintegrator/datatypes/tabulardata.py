from __future__ import annotations

import re
import urllib.parse
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class TabularData(BaseDataType):
    """
    Implements the Wikibase data type 'tabular-data'
    """
    DTYPE = WikibaseDatatype.TABULARDATA
    PTYPE = 'http://wikiba.se/ontology#TabularData'
    # The RDF export identifies the value by the URL of its page on Wikimedia Commons
    SPARQL_IRI_PREFIX = 'http://commons.wikimedia.org/data/main/'

    def __init__(self, value: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: Reference to tabular data file on Wikimedia Commons.
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Taipei+Population.tab
            pattern = re.compile(r'^Data:((?![:|#]).)+\.tab$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .tab. In addition title should not contain characters like colon, hash or pipe.")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        The RDF representation is the full Wikimedia Commons URL of the file (e.g.
        http://commons.wikimedia.org/data/main/Data:Population+FR+Q1657686.tab), only the page title is kept.

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

        pattern = re.compile(r'^.+/(Data:.+\.tab)$')
        # Encoded like MediaWiki's wfUrlencode(): a space is a '+'
        matches = pattern.match(urllib.parse.unquote_plus(value))
        if not matches:
            raise ValueError(f"Invalid SPARQL value {value}")

        self.set_value(value=str(matches.group(1)))

        return self

    def get_sparql_value(self, **kwargs: Any) -> str | None:
        """
        The IRI of the value in the RDF export: the URL of the page on Wikimedia Commons, with the page title encoded like
        MediaWiki's wfUrlencode() (a space is a '+', ':' and '/' are kept), e.g. <http://commons.wikimedia.org/data/main/Data:Paris.map>
        """
        if self.mainsnak.snaktype != WikibaseSnakType.KNOWN_VALUE:
            return None
        return '<' + self.SPARQL_IRI_PREFIX + urllib.parse.quote_plus(self.mainsnak.datavalue['value'], safe=";@$!*(),/~:") + '>'
