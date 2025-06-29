from wikibaseintegrator.datatypes.string import String


class ExternalID(String):
    """
    Implements the Wikibase data type 'external-id'
    """
    DTYPE = 'external-id'
    PTYPE = 'http://wikiba.se/ontology#ExternalId'
