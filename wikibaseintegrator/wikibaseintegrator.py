from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.mediainfo import MediaInfo
from wikibaseintegrator.entities.property import Property


class WikibaseIntegrator:

    def __init__(self,
                 is_bot=False,
                 login=None):
        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login

        # Quick access to entities
        self.item = Item(api=self)
        self.property = Property(api=self)
        self.lexeme = Lexeme(api=self)
        self.mediainfo = MediaInfo(api=self)
