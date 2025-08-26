from typing import Any, Optional

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class String(BaseDataType):
    """
    Implements the Wikibase data type 'string'
    """

    DTYPE = 'string'

    def __init__(self, value: Optional[str] = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The string to be used as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: Optional[str] = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value and ('\n' in value or '\r' in value):
            raise ValueError("String value must not contain new line character")

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
