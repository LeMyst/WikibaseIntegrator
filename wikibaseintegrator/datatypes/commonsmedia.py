import re
import urllib.parse

from wikibaseintegrator.datatypes.string import String


class CommonsMedia(String):
    """
    Implements the Wikibase data type for Wikimedia commons media files
    """
    DTYPE = 'commonsMedia'

    def get_sparql_value(self) -> str:
        return '<' + self.mainsnak.datavalue['value'] + '>'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^<?.*?/?([^/]*?)>?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(value=urllib.parse.unquote(matches.group(1)))
        return True
