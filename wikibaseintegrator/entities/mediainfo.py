"""
MediaInfo entity, used by Structured Data on Commons (SDC).

.. warning::
    Beta: Structured Data on Commons has no stable interface policy (https://phabricator.wikimedia.org/T149410) and its
    API is not versioned, so it can change without notice. This module follows these changes and may change in a minor
    release, without a deprecation period.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Self

from wikibaseintegrator.entities.baseentity import BaseEntity, TermsEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.wbi_exceptions import MissingEntityException
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

if TYPE_CHECKING:
    from wikibaseintegrator.wbi_login import _Login


class MediaInfoEntity(TermsEntity):
    """
    A MediaInfo entity (M-ID), holding the structured data of a media file hosted on Wikimedia Commons.

    .. warning::
        Beta: Structured Data on Commons has no stable interface policy, see the module documentation.
    """
    ETYPE = 'mediainfo'

    def __init__(self, labels: Labels | None = None, descriptions: Descriptions | None = None, aliases: Aliases | None = None, **kwargs: Any) -> None:
        """

        :param api:
        :param labels:
        :param descriptions:
        :param aliases:
        :param sitelinks:
        :param kwargs:
        """
        super().__init__(labels=labels, descriptions=descriptions, aliases=aliases, **kwargs)

    @BaseEntity.id.setter  # type: ignore
    def id(self, value: None | str | int) -> None:
        if isinstance(value, str):
            pattern = re.compile(r'^M?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid MediaInfo ID ({value}), format must be 'M[0-9]+'")

            value = f'M{matches.group(1)}'
        elif isinstance(value, int):
            value = f'M{value}'
        elif value is None:
            pass
        else:
            raise ValueError(f"Invalid MediaInfo ID ({value}), format must be 'M[0-9]+'")

        BaseEntity.id.fset(self, value)  # type: ignore

    def new(self, **kwargs: Any) -> MediaInfoEntity:
        return MediaInfoEntity(api=self.api, **kwargs)

    def get(self, entity_id: str | int | None = None, **kwargs: Any) -> MediaInfoEntity:
        """
        Request the MediaWiki API to get data for the entity specified in argument.

        :param entity_id: The ID of the entity to load, starting with 'M'. By default, the ID of this entity, to reload it.
        :param kwargs:
        :return: a MediaInfoEntity instance
        """

        if entity_id is None and self.id is not None:
            entity_id = self.id
        elif entity_id is None:
            raise ValueError("You must provide an entity_id")

        if isinstance(entity_id, str):
            pattern = re.compile(r'^M?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid MediaInfo ID ({entity_id}), format must be 'M[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("MediaInfo ID must be greater than 0")

        entity_id = f'M{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return MediaInfoEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_by_title(self, titles: list[str] | str, sites: str = 'commonswiki', login: _Login | None = None, allow_anonymous: bool = True, is_bot: bool | None = None,
                     **kwargs: Any) -> MediaInfoEntity:
        """
        Request the MediaWiki API to get the MediaInfo entity of a file, from the title of its page.

        :param titles: The title of the file page, e.g. 'File:Example.jpg'
        :param sites: The site of the page. Wikimedia Commons ('commonswiki') by default.
        :param login: A login instance. The login of the WikibaseIntegrator instance by default.
        :param allow_anonymous: Allow an anonymous request. Enabled by default.
        :param is_bot: Add the bot flag to the request. The is_bot of the WikibaseIntegrator instance by default.
        :param kwargs: More arguments for mediawiki_api_call_helper()
        :return: a MediaInfoEntity instance
        :exception MissingEntityException: If the page doesn't exist.
        :exception ValueError: If the titles match more than one entity.
        """
        if isinstance(titles, list):
            titles = '|'.join(titles)

        params = {
            'action': 'wbgetentities',
            'sites': sites,
            'titles': titles,
            'format': 'json'
        }

        login = login or self.api.login
        is_bot = is_bot if is_bot is not None else self.api.is_bot

        json_data = mediawiki_api_call_helper(data=params, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)

        entities = json_data['entities']
        # The API answers {'-1': {'title': ..., 'missing': ''}} for a page that doesn't exist
        missing = [entity.get('title', entity_id) for entity_id, entity in entities.items() if 'missing' in entity]
        if len(entities) == 0 or missing:
            raise MissingEntityException(f"Title not found: {', '.join(missing) or titles}")
        if len(entities) > 1:
            raise ValueError('More than one element for this title')

        return MediaInfoEntity(api=self.api).from_json(json_data=next(iter(entities.values())))

    def get_json(self) -> dict[str, str | dict]:
        json_data = {
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            **super().get_json()
        }

        if 'claims' in json_data:  # MediaInfo change name of 'claims' to 'statements'
            json_data['statements'] = json_data.pop('claims')

        if isinstance(json_data, dict) and 'statements' in json_data and isinstance(json_data['statements'], dict):
            for statements in json_data['statements'].values():
                for statement in statements:
                    if isinstance(statement, dict) and 'mainsnak' in statement:
                        if isinstance(statement['mainsnak'], dict) and 'datatype' in statement['mainsnak']:
                            del statement['mainsnak']['datatype']

        return json_data

    def from_json(self, json_data: dict[str, Any]) -> Self:
        super().from_json(json_data=json_data)
        super()._terms_from_json(json_data=json_data)

        if 'statements' in json_data:
            self.claims = Claims().from_json(json_data['statements'])

        return self

    def write(self, **kwargs: Any) -> MediaInfoEntity:
        """
        Write the MediaInfoEntity data to the Wikibase instance and return the MediaInfoEntity object returned by the instance.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: Clear the existing entity before updating
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: an MediaInfoEntity of the response from the instance
        """
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
