import re
from typing import Any

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

    def __init__(self, value: str = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The URL to be used as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str = None):
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

    def get_sparql_value(self) -> str:
        return '<' + self.mainsnak.datavalue['value'] + '>'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^<?(.*?)>?$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(value=matches.group(1))

        return True
