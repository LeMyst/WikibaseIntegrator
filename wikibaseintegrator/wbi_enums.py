from enum import Enum, auto


class ActionIfExists(Enum):
    """
    Action to take if a statement with a property already exists on the entity.

    APPEND_OR_REPLACE: Add the new element to the property if it does not exist, otherwise replace the existing element.
    FORCE_APPEND: Forces the addition of the new element to the property, even if it already exists.
    KEEP: Does nothing if the property already has elements stated.
    REPLACE_ALL: Replace all elements with the same property number.
    MERGE_REFS_OR_APPEND: Add the new element to the property if it does not exist, otherwise merge the references, adding the references for the new claim as a new reference block.
    """
    APPEND_OR_REPLACE = auto()
    FORCE_APPEND = auto()
    KEEP = auto()
    REPLACE_ALL = auto()
    MERGE_REFS_OR_APPEND = auto()


class WikibaseDatatype(Enum):
    COMMONSMEDIA = 'commonsMedia'
    EDTF = 'edtf'
    ENTITYSCHEMA = 'entity-schema'
    EXTERNALID = 'external-id'
    FORM = 'wikibase-form'
    GEOSHAPE = 'geo-shape'
    GLOBECOORDINATE = 'globe-coordinate'
    ITEM = 'wikibase-item'
    LEXEME = 'wikibase-lexeme'
    LOCALMEDIA = 'localMedia'
    MATH = 'math'
    MONOLINGUALTEXT = 'monolingualtext'
    MUSICALNOTATION = 'musical-notation'
    PROPERTY = 'wikibase-property'
    QUANTITY = 'quantity'
    SENSE = 'wikibase-sense'
    STRING = 'string'
    TABULARDATA = 'tabular-data'
    TIME = 'time'
    URL = 'url'


class WikibaseRank(Enum):
    DEPRECATED = "deprecated"
    NORMAL = "normal"
    PREFERRED = "preferred"


class WikibaseSnakType(Enum):
    """
    The snak type of the Wikibase data snak, three values possible,
    depending if the value is a known (value), not existent (novalue) or
    unknown (somevalue). See Wikibase documentation.
    """
    KNOWN_VALUE = "value"
    NO_VALUE = "novalue"
    UNKNOWN_VALUE = "somevalue"


class WikibaseTimePrecision(Enum):
    # SECOND = 14  # UNSUPPORTED TO DATE (REL1_37)
    # MINUTE = 13  # UNSUPPORTED TO DATE (REL1_37)
    # HOUR = 12  # UNSUPPORTED TO DATE (REL1_37)
    DAY = 11
    MONTH = 10
    YEAR = 9
    DECADE = 8
    CENTURY = 7
    MILLENNIUM = 6
    TEN_THOUSAND_YEARS = 5
    HUNDRED_THOUSAND_YEARS = 4
    MILLION_YEARS = 3
    TEN_MILLION_YEARS = 2
    HUNDRED_MILLION_YEARS = 1
    BILLION_YEARS = 0


class EntityField(Enum):
    """
    The different fields of an entity.
    Used to specify which field to update when updating an entity.
    """
    # BaseEntity field
    CLAIMS = auto()

    # Item fields (and partly MediaInfo and Property fields)
    ALIASES = auto()
    DESCRIPTIONS = auto()
    LABELS = auto()
    SITELINKS = auto()

    # Lexeme fields
    LEMMAS = auto()
    LEXICAL_CATEGORY = auto()
    LANGUAGE = auto()
    FORMS = auto()
    SENSES = auto()
