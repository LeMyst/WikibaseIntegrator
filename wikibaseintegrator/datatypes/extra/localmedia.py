from wikibaseintegrator.datatypes import String


class LocalMedia(String):
    """
    Implements the Wikibase data type for Wikibase Local Media extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media
    """
    DTYPE = 'localMedia'
