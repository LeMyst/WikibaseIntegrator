from __future__ import annotations

import re

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels


class Property(BaseEntity):
    ETYPE = 'property'

    def __init__(self, api, datatype=None, labels=None, descriptions=None, aliases=None, **kwargs):
        self.api = api

        super().__init__(api=api, **kwargs)

        self.json = None

        # Property specific
        self.datatype = datatype

        # Items and property specific
        self.labels = labels or Labels()
        self.descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    def new(self, **kwargs) -> Property:
        return Property(self.api, **kwargs)

    def get(self, entity_id, **kwargs) -> Property:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError("Invalid property ID ({}), format must be 'P[0-9]+'".format(entity_id))

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Property ID must be greater than 0")

        entity_id = 'P{}'.format(entity_id)
        json_data = super().get(entity_id=entity_id, **kwargs)
        return Property(self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> {}:
        return {
            'datatype': self.datatype,
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super().get_json()
        }

    def from_json(self, json_data) -> Property:
        super().from_json(json_data=json_data)

        self.datatype = json_data['datatype']
        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])

        return self

    def write(self, **kwargs):
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
