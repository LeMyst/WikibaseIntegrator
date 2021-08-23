from __future__ import annotations

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.models.sitelinks import Sitelinks


class Item(BaseEntity):
    ETYPE = 'item'

    def __init__(self, api, labels=None, descriptions=None, aliases=None, sitelinks=None, **kwargs) -> None:
        """

        :param api:
        :param labels:
        :param descriptions:
        :param aliases:
        :param sitelinks:
        :param kwargs:
        """
        self.api = api

        super(Item, self).__init__(api=self.api, **kwargs)

        # Item and property specific
        self.labels = labels or Labels()
        self.descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

        # Item specific
        self.sitelinks = sitelinks or Sitelinks()

    def new(self, **kwargs) -> Item:
        return Item(self.api, **kwargs)

    def get(self, entity_id, **kwargs) -> Item:
        json_data = super(Item, self).get(entity_id=entity_id, **kwargs)
        return Item(self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> {}:
        return {
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super(Item, self).get_json()
        }

    def from_json(self, json_data) -> Item:
        super(Item, self).from_json(json_data=json_data)

        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])
        self.sitelinks = Sitelinks().from_json(json_data['sitelinks'])

        return self

    def write(self, allow_anonymous=False):
        json_data = super(Item, self)._write(data=self.get_json(), allow_anonymous=allow_anonymous)
        return self.from_json(json_data=json_data)
