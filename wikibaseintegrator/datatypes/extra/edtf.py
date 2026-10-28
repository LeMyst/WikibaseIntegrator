from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class EDTF(String):
    """
    Implements the Wikibase data type for Wikibase Extended Date/Time Format extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF
    """
    DTYPE = WikibaseDatatype.EDTF
