import re
from typing import Any, Optional, Union

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class Lexeme(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-lexeme'
    """
    DTYPE = 'wikibase-lexeme'
    PTYPE = 'http://wikiba.se/ontology#WikibaseLexeme'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value: Optional[Union[str, int]] = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The lexeme number to serve as a value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: Optional[Union[str, int]] = None):
        assert isinstance(value, (str, int)) or value is None, f"Expected str or int, found {type(value)} ({value})"

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^(?:[a-zA-Z]+:|.+\/entity\/)?L?([0-9]+)$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError(f"Invalid lexeme ID ({value}), format must be 'L[0-9]+'")

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'lexeme',
                    'numeric-id': value,
                    'id': f'L{value}'
                },
                'type': 'wikibase-entityid'
            }

    def get_sparql_value(self, **kwargs: Any) -> Optional[str]:
        if self.mainsnak.snaktype == WikibaseSnakType.KNOWN_VALUE:
            wikibase_url = str(kwargs['wikibase_url'] if 'wikibase_url' in kwargs else config['WIKIBASE_URL'])
            return f'<{wikibase_url}/entity/' + self.mainsnak.datavalue['value']['id'] + '>'

        return None
