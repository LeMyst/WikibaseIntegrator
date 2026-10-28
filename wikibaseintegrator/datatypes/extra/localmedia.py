from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class LocalMedia(String):
    """
    Implements the Wikibase data type for Wikibase Local Media extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media
    """
    DTYPE = WikibaseDatatype.LOCALMEDIA
