import re
from typing import Any, Optional

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class EntitySchema(BaseDataType):
    """
    Implements the Wikibase data type 'entity-schema'
    """
    DTYPE = 'entity-schema'

    def __init__(self, value: Optional[str] = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The EntitySchema ID to serve as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: Optional[str] = None):
        assert isinstance(value, str) or value is None, f'Expected str, found {type(value)} ({value})'

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^E[0-9]+$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError(f"Invalid Entity Schema ({value}), format must be 'E[0-9]+'")

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'entity-schema',
                    'id': value
                },
                'type': 'wikibase-entityid'
            }