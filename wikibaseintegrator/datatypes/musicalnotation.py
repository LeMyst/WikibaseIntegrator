from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class MusicalNotation(String):
    """
    Implements the Wikibase data type 'musical-notation'
    """
    DTYPE = WikibaseDatatype.MUSICALNOTATION
    PTYPE = 'http://wikiba.se/ontology#MusicalNotation'

    def set_value(self, value: str | None = None) -> None:
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
