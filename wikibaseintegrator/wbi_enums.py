from enum import Enum, auto


class ActionIfExists(Enum):
    """
    Action to take if a statement with a property already exists on the item or lexeme.
    """
    APPEND = auto()
    FORCE_APPEND = auto()
    KEEP = auto()
    REPLACE = auto()


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
