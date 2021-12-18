from __future__ import annotations

import re
from typing import Any, List, Type, Union

from wikibaseintegrator.models import Claim


class BaseDataType(Claim):
    """
    The base class for all Wikibase data types, they inherit from it
    """
    DTYPE = 'base-data-type'
    subclasses: List[Type[BaseDataType]] = []
    sparql_query: str = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}' .
        }}
    '''

    def __init__(self, prop_nr: Union[int, str] = None, **kwargs: Any):
        """
        Constructor, will be called by all data types.

        :param prop_nr: The property number a Wikibase snak belongs to
        """

        super().__init__(**kwargs)

        self.mainsnak.property_number = prop_nr or None
        # self.subclasses.append(self)

    # Allow registration of subclasses of BaseDataType into BaseDataType.subclasses
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

    def set_value(self, value: Any = None):
        pass

    def get_sparql_value(self) -> str:
        return '"' + self.mainsnak.datavalue['value'] + '"'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        if type == 'uri':
            pattern = re.compile(r'^<?(.*?)>?$')
            matches = pattern.match(value)
            if not matches:
                return False

            self.set_value(value=matches.group(1))
        elif type == 'literal':
            pattern = re.compile(r'^"?(.*?)"?$')
            matches = pattern.match(value)
            if not matches:
                return False

            self.set_value(value=matches.group(1))
        else:
            raise ValueError

        return True
