import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class URL(BaseDataType):
    """
    Implements the Wikibase data type for URL strings
    """
    DTYPE = 'url'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value: str = None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The URL to be used as the value
        """

        super().__init__(**kwargs)

        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            pattern = re.compile(r'^([a-z][a-z\d+.-]*):([^][<>\"\x00-\x20\x7F])+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid URL {value}")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
