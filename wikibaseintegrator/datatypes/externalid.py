from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class ExternalID(String):
    """
    Implements the Wikibase data type 'external-id'
    """
    DTYPE = WikibaseDatatype.EXTERNALID
    PTYPE = 'http://wikiba.se/ontology#ExternalId'
