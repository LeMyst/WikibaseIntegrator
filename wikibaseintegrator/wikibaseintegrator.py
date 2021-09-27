from __future__ import annotations

from typing import TYPE_CHECKING

from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.mediainfo import MediaInfo
from wikibaseintegrator.entities.property import Property

if TYPE_CHECKING:
    from wikibaseintegrator.wbi_login import Login


class WikibaseIntegrator:

    def __init__(self, is_bot: bool = False, login: Login = None):
        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login

        # Quick access to entities
        self.item = Item(api=self)
        self.property = Property(api=self)
        self.lexeme = Lexeme(api=self)
        self.mediainfo = MediaInfo(api=self)
