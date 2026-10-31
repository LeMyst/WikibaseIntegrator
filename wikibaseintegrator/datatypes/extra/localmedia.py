from __future__ import annotations

import urllib.parse
from typing import Self

from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class LocalMedia(String):
    """
    Implements the Wikibase data type for Wikibase Local Media extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media
    """
    DTYPE = WikibaseDatatype.LOCALMEDIA
    # Wikibase builds the URI from the data type ID ('localMedia'), the extension doesn't set one
    PTYPE = 'http://wikiba.se/ontology#LocalMedia'

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        The extension writes the URL of the file page on the instance (e.g. https://wiki.example.org/wiki/File:Bunny_rabbit.jpg,
        or index.php?title=File:Bunny_rabbit.jpg), only the file name is kept: without the namespace, which can be localized
        (Fichier:...), and with spaces instead of underscores.

        The partial load of the fast run mode (without cache) still queries the file name as a literal, which matches
        nothing: building the URL needs the article path of the instance.

        :param sparql_value: A SPARQL value composed of type and value
        :return: The object itself
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'uri':
            raise ValueError(f"Wrong SPARQL type {type}")

        url = urllib.parse.urlparse(value)
        title = urllib.parse.parse_qs(url.query).get('title', [''])[0] or urllib.parse.unquote(url.path.rsplit('/', 1)[-1])
        if ':' not in title:
            raise ValueError(f"Not the URL of a file page: {value}")

        self.set_value(value=title.split(':', 1)[1].replace('_', ' '))

        return self
