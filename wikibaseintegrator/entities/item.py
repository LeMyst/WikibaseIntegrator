from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models import LanguageValues
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.models.sitelinks import Sitelinks


class ItemEntity(BaseEntity):
    ETYPE = 'item'

    def __init__(self, labels: Labels | None = None, descriptions: Descriptions | None = None, aliases: Aliases | None = None, sitelinks: Sitelinks | None = None, **kwargs: Any) -> None:
        """

        :param api:
        :param labels:
        :param descriptions:
        :param aliases:
        :param sitelinks:
        :param kwargs:
        """
        super().__init__(**kwargs)

        # Item, Property and MediaInfo specific
        self.labels: LanguageValues = labels or Labels()
        self.descriptions: LanguageValues = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

        # Item specific
        self.sitelinks = sitelinks or Sitelinks()

    @BaseEntity.id.setter  # type: ignore
    def id(self, value: None | str | int):
        if isinstance(value, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?Q?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid item ID ({value}), format must be 'Q[0-9]+'")

            value = f'Q{matches.group(1)}'
        elif isinstance(value, int):
            value = f'Q{value}'
        elif value is None:
            pass
        else:
            raise ValueError(f"Invalid item ID ({value}), format must be 'Q[0-9]+'")

        BaseEntity.id.fset(self, value)  # type: ignore

    @property
    def labels(self) -> Labels:
        return self.__labels

    @labels.setter
    def labels(self, labels: Labels):
        if not isinstance(labels, Labels):
            raise TypeError
        self.__labels = labels

    @property
    def descriptions(self) -> Descriptions:
        return self.__descriptions

    @descriptions.setter
    def descriptions(self, descriptions: Descriptions):
        if not isinstance(descriptions, Descriptions):
            raise TypeError
        self.__descriptions = descriptions

    @property
    def aliases(self) -> Aliases:
        return self.__aliases

    @aliases.setter
    def aliases(self, aliases: Aliases):
        if not isinstance(aliases, Aliases):
            raise TypeError
        self.__aliases = aliases

    @property
    def sitelinks(self) -> Sitelinks:
        return self.__sitelinks

    @sitelinks.setter
    def sitelinks(self, sitelinks: Sitelinks):
        if not isinstance(sitelinks, Sitelinks):
            raise TypeError
        self.__sitelinks = sitelinks

    def new(self, **kwargs: Any) -> ItemEntity:
        return ItemEntity(api=self.api, **kwargs)

    def get(self, entity_id: str | int | None = None, **kwargs: Any) -> ItemEntity:
        """
        Request the MediaWiki API to get data for the entity specified in argument.

        :param entity_id: The entity_id of the Item entity you want. Must start with a 'Q'.
        :param kwargs:
        :return: an ItemEntity instance
        """

        if entity_id is None and self.id is not None:
            entity_id = self.id
        elif entity_id is None:
            raise ValueError("You must provide an entity_id")

        if isinstance(entity_id, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?Q?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid item ID ({entity_id}), format must be 'Q[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Item ID must be greater than 0")

        entity_id = f'Q{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return ItemEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> dict[str, str | dict]:
        """
        To get the dict equivalent of the JSON representation of the Item.

        :return: A dict representation of the Item.
        """
        return {
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super().get_json()
        }

    def from_json(self, json_data: dict[str, Any]) -> ItemEntity:
        super().from_json(json_data=json_data)

        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])
        self.sitelinks = Sitelinks().from_json(json_data['sitelinks'])

        return self

    def write(self, **kwargs: Any) -> ItemEntity:
        """
        Write the ItemEntity data to the Wikibase instance and return the ItemEntity object returned by the instance.
        extend :func:`~wikibaseintegrator.entities.BaseEntity._write`

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: Clear the existing entity before updating
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: an ItemEntity of the response from the instance
        """
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
