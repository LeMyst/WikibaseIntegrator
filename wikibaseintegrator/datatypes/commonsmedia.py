import re
import urllib.parse
from typing import Optional

from wikibaseintegrator.datatypes.url import URL


class CommonsMedia(URL):
    """
    Implements the Wikibase data type for Wikimedia commons media files
    """
    DTYPE = 'commonsMedia'
    PTYPE = 'http://wikiba.se/ontology#CommonsMedia'

    def set_value(self, value: Optional[str] = None):
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

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^<?.*?/?([^/]*?)>?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(value=urllib.parse.unquote(matches.group(1)))
        return True
