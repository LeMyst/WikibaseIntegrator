from __future__ import annotations

import re
import urllib.parse
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class GeoShape(BaseDataType):
    """
    Implements the Wikibase data type 'geo-shape'
    """
    DTYPE = 'geo-shape'
    PTYPE = 'http://wikiba.se/ontology#GeoShape'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The GeoShape map file name in Wikimedia Commons to be linked
        :param kwargs:

        :Keyword Arguments:
            * *prop_nr* (``str``) --
              The item ID for this claim
            * *snaktype* (``str``) --
              The snak type, either 'value', 'somevalue' or 'novalue'
            * *references* (``References`` or list of ``Claim``) --
              List with reference objects
            * *qualifiers* (``Qualifiers``) --
              List with qualifier objects
            * *rank* (``WikibaseRank``) --
              The snak type, either 'value', 'somevalue' or 'novalue'
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Paris.map
            pattern = re.compile(r'^Data:((?![:|#]).)+\.map$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .map. In addition title should not contain characters like colon, hash or pipe.")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }

    def from_sparql_value(self, sparql_value: dict) -> GeoShape:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        The RDF representation is the full Wikimedia Commons URL of the map (e.g.
        http://commons.wikimedia.org/data/main/Data:Paris.map), only the page title is kept.

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
            pattern = re.compile(r'^.+/(Data:.+\.map)$')
            matches = pattern.match(urllib.parse.unquote(value))
            if not matches:
                raise ValueError(f"Invalid SPARQL value {value}")

            self.set_value(value=str(matches.group(1)))

        return self

    # TODO: Does GeoShape need a full URL to wikimedia commons?
    def get_sparql_value(self, **kwargs: Any) -> str:
        return '<' + self.mainsnak.datavalue['value'] + '>'
