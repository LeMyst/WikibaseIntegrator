from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class String(BaseDataType):
    """
    Implements the Wikibase data type 'string'
    """

    DTYPE = 'string'

    def __init__(self, value: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The string to be used as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | None = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value and ('\n' in value or '\r' in value):
            raise ValueError("String value must not contain newline character")

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
