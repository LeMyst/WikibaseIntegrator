import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class TabularData(BaseDataType):
    """
    Implements the Wikibase data type 'tabular-data'
    """
    DTYPE = 'tabular-data'

    def __init__(self, value: str = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: Reference to tabular data file on Wikimedia Commons.
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Taipei+Population.tab
            pattern = re.compile(r'^Data:((?![:|#]).)+\.tab$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .tab. In addition title should not contain characters like colon, hash or pipe.")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
