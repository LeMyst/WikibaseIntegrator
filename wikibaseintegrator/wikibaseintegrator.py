"""
Main class of the Library.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

from wikibaseintegrator.entities.item import ItemEntity
from wikibaseintegrator.entities.lexeme import LexemeEntity
from wikibaseintegrator.entities.mediainfo import MediaInfoEntity
from wikibaseintegrator.entities.property import PropertyEntity
from wikibaseintegrator.wbi_config import config as wbi_config

if TYPE_CHECKING:
    from wikibaseintegrator.wbi_login import BaseLogin


class _InstanceConfig(Mapping[str, Any]):
    """
    The configuration of a WikibaseIntegrator instance, read-only: its own values, then the ones of wbi_config, read when they're
    used, so that a change of wbi_config applies to the options the instance doesn't set.
    """

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)

    def __getitem__(self, key: str) -> Any:
        return self._values[key] if key in self._values else wbi_config[key]

    def __iter__(self) -> Iterator[str]:
        return iter({**wbi_config, **self._values})

    def __len__(self) -> int:
        return len({**wbi_config, **self._values})

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._values!r})'

    def __deepcopy__(self, memo: dict[int, Any]) -> _InstanceConfig:
        # Read-only: a copy of an entity keeps the configuration of its instance, still backed by wbi_config
        return self


class WikibaseIntegrator:

    def __init__(self, is_bot: bool = False, login: BaseLogin | None = None, config: Mapping[str, Any] | None = None) -> None:
        """
        This function initializes a WikibaseIntegrator instance to quickly access different entity type instances.

        :param is_bot: declare if the bot flag must be set when you interact with the MediaWiki API.
        :param login: a wbi_login instance needed when you try to access a restricted MediaWiki instance.
        :param config: The configuration of this instance, with the keys of wbi_config, e.g. ``{'MEDIAWIKI_API_URL': ...,
            'SPARQL_ENDPOINT_URL': ..., 'WIKIBASE_URL': ...}`` or ``get_manifest(url).config()``. The keys it doesn't set
            are read from wbi_config, when they're used. The entities of this instance (``item``, ``property``,
            ``lexeme``, ``mediainfo``) use its MEDIAWIKI_API_URL, USER_AGENT, MAX_REQUEST_SIZE, WIKIBASE_URL,
            SPARQL_ENDPOINT_URL (fast run) and DEFAULT_LEXEME_LANGUAGE. The other options are read from wbi_config.
        :raises ValueError: If a key of config isn't an option of wbi_config
        """
        unknown = sorted(set(config or {}) - set(wbi_config))
        if unknown:
            raise ValueError(f"Unknown configuration options: {', '.join(unknown)}. The options are the keys of wbi_config: {', '.join(wbi_config)}.")

        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login
        #: The configuration of this instance, read-only: the values given to the constructor, and wbi_config for the others.
        self.config: Mapping[str, Any] = _InstanceConfig(config or {})

        # Quick access to entities
        self.item = ItemEntity(api=self)
        self.property = PropertyEntity(api=self)
        self.lexeme = LexemeEntity(api=self)
        self.mediainfo = MediaInfoEntity(api=self)  # Beta, see wikibaseintegrator.entities.mediainfo
