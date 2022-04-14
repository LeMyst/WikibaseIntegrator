"""
Main class of the Library.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from wikibaseintegrator.entities.item import ItemEntity
from wikibaseintegrator.entities.lexeme import LexemeEntity
from wikibaseintegrator.entities.mediainfo import MediaInfoEntity
from wikibaseintegrator.entities.property import PropertyEntity

if TYPE_CHECKING:
    from wikibaseintegrator.wbi_login import _Login


class WikibaseIntegrator:

    def __init__(self, is_bot: bool = False, login: _Login = None):
        """
        This function initializes a WikibaseIntegrator instance to quickly access different entity type instances.

        :param is_bot: declare if the bot flag must be set when you interact with the MediaWiki API.
        :param login: a wbi_login instance needed when you try to access a restricted MediaWiki instance.
        """
        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login

        # Quick access to entities
        self.item = ItemEntity(api=self)
        self.property = PropertyEntity(api=self)
        self.lexeme = LexemeEntity(api=self)
        self.mediainfo = MediaInfoEntity(api=self)
