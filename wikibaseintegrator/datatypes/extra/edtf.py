from wikibaseintegrator.datatypes.string import String


class EDTF(String):
    """
    Implements the Wikibase data type for Wikibase Extended Date/Time Format extension.
    More info at https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF
    """
    DTYPE = 'edtf'
