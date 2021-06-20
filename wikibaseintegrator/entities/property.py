from __future__ import annotations

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels


class Property(BaseEntity):
    ETYPE = 'property'

    def __init__(self, api, datatype=None, labels=None, descriptions=None, aliases=None, **kwargs):
        self.api = api

        super().__init__(api=api, entity_type='property', **kwargs)

        self.json = None

        # Property specific
        self.datatype = datatype

        # Items and property specific
        self.labels = labels or Labels()
        self.descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    def get(self, entity_id) -> Property:
        json_data = super(Property, self).get(entity_id=entity_id)
        return Property(self.api).from_json(json_data=json_data['entities'][entity_id])

    def from_json(self, json_data) -> Property:
        super(Property, self).from_json(json_data=json_data)

        self.datatype = json_data['datatype']
        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])

        return self
