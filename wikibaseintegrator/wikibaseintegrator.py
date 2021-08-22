from enum import Enum

from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.mediainfo import MediaInfo
from wikibaseintegrator.entities.property import Property

class ActionIfExists(Enum):
    """
    Action to take if a statement with a property already 
    exists on the item or lexeme.
    """
    APPEND = 0
    REPLACE = 1

class WikibaseIntegrator(object):

    def __init__(self,
                 search_only=False,
                 is_bot=False,
                 login=None):
        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login
        self.search_only = search_only or False

        # Quick access to entities
        self.item = Item(api=self)
        self.property = Property(api=self)
        self.lexeme = Lexeme(api=self)
        self.mediainfo = MediaInfo(api=self)

        # Helpers
        self.helpers = wbi_helpers
