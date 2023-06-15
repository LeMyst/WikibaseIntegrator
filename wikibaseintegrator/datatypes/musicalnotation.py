from typing import Optional

from wikibaseintegrator.datatypes.string import String


class MusicalNotation(String):
    """
    Implements the Wikibase data type 'musical-notation'
    """
    DTYPE = 'musical-notation'

    def set_value(self, value: Optional[str] = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
