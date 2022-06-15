from enum import Enum, auto

from wikibaseintegrator.datatypes import (URL, CommonsMedia, ExternalID, Form, GeoShape, GlobeCoordinate, Item, Lexeme, Math, MonolingualText, MusicalNotation, Property, Quantity,
                                          Sense, String, TabularData, Time)


class ActionIfExists(Enum):
    """
    Action to take if a statement with a property already exists on the item or lexeme.
    """
    APPEND = auto()
    FORCE_APPEND = auto()
    KEEP = auto()
    REPLACE = auto()


class WikibaseDatatype(Enum):
    COMMONSMEDIA = CommonsMedia.DTYPE
    EXTERNALID = ExternalID.DTYPE
    FORM = Form.DTYPE
    GEOSHAPE = GeoShape.DTYPE
    GLOBECOORDINATE = GlobeCoordinate.DTYPE
    ITEM = Item.DTYPE
    LEXEME = Lexeme.DTYPE
    MATH = Math.DTYPE
    MONOLINGUALTEXT = MonolingualText.DTYPE
    MUSICALNOTATION = MusicalNotation.DTYPE
    PROPERTY = Property.DTYPE
    QUANTITY = Quantity.DTYPE
    SENSE = Sense.DTYPE
    STRING = String.DTYPE
    TABULARDATA = TabularData.DTYPE
    TIME = Time.DTYPE
    URL = URL.DTYPE


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


class WikibaseDatePrecision(Enum):
    # SECOND = 14  # UNSUPPORTED TO DATE (REL1_37)
    # MINUTE = 13  # UNSUPPORTED TO DATE (REL1_37)
    # HOUR = 12  # UNSUPPORTED TO DATE (REL1_37)
    DAY = 11
    MONTH = 10
    YEAR = 9
    DECADE = 8
    CENTURY = 7
    MILLENNIUM = 6
    HUNDRED_THOUSAND_YEARS = 4
    MILLION_YEARS = 3
    BILLION_YEARS = 0
