import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class GeoShape(BaseDataType):
    """
    Implements the Wikibase data type 'geo-shape'
    """
    DTYPE = 'geo-shape'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value: str = None, **kwargs: Any):
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

    def set_value(self, value: str = None):
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
