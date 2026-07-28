from __future__ import annotations

import re
import urllib.parse

from wikibaseintegrator.datatypes.url import URL
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class CommonsMedia(URL):
    """
    Implements the Wikibase data type for Wikimedia commons media files
    """
    DTYPE = 'commonsMedia'
    PTYPE = 'http://wikiba.se/ontology#CommonsMedia'

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            pattern = re.compile(r'^.+\..+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid CommonsMedia {value}")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }

    def from_sparql_value(self, sparql_value: dict) -> CommonsMedia:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        The RDF representation is the full Wikimedia Commons URL of the file (e.g.
        http://commons.wikimedia.org/wiki/Special:FilePath/Example%20file.jpg), only the file name is kept.
        Without this, the URL implementation inherited by this class would store the whole URL, which would never
        match the file name held by a local claim.

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
            self.set_value(value=urllib.parse.unquote(value.rsplit('/', 1)[-1]))

        return self

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^<?.*?/?([^/]*?)>?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(value=urllib.parse.unquote(matches.group(1)))
        return True
