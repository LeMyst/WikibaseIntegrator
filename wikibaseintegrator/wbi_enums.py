from enum import Enum


class ActionIfExists(Enum):
    """
    Action to take if a statement with a property already
    exists on the item or lexeme.
    """
    APPEND = 0
    FORCE_APPEND = 1
    KEEP = 2
    REPLACE = 3


class WikibaseRank(Enum):
    DEPRECATED = "deprecated"
    NORMAL = "normal"
    PREFERRED = "preferred"


class WikibaseSnakValueType(Enum):
    """
    The snak type of the Wikibase data snak, three values possible, 
    depending if the value is a known (value), not existent (novalue) or
    unknown (somevalue). See Wikibase documentation.
    """
    KNOWN_VALUE = "value"
    NO_VALUE = "novalue"
    UNKNOWN_VALUE = "somevalue"
