from __future__ import annotations

import re
from typing import Any, Dict, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models import LanguageValues
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels


class Property(BaseEntity):
    ETYPE = 'property'

    def __init__(self, datatype: str = None, labels: Labels = None, descriptions: Descriptions = None, aliases: Aliases = None, **kwargs: Any):
        super().__init__(**kwargs)

        # Property specific
        self.datatype = datatype

        # Items and property specific
        self.labels: LanguageValues = labels or Labels()
        self.descriptions: LanguageValues = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    def new(self, **kwargs: Any) -> Property:
        return Property(api=self.api, **kwargs)

    def get(self, entity_id: Union[str, int], **kwargs: Any) -> Property:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid property ID ({entity_id}), format must be 'P[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Property ID must be greater than 0")

        entity_id = f'P{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return Property(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> Dict[str, Union[str, dict]]:
        return {
            'datatype': str(self.datatype),
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super().get_json()
        }

    def from_json(self, json_data: Dict[str, Any]) -> Property:
        super().from_json(json_data=json_data)

        self.datatype = json_data['datatype']
        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])

        return self

    def write(self, **kwargs: Any) -> Property:
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
