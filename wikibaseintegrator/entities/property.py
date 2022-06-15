from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.wbi_enums import WikibaseDatatype


class PropertyEntity(BaseEntity):
    ETYPE = 'property'

    def __init__(self, datatype: str = None, labels: Labels = None, descriptions: Descriptions = None, aliases: Aliases = None, **kwargs: Any):
        super().__init__(**kwargs)

        # Property specific
        if datatype is not None:
            self.datatype = WikibaseDatatype(datatype)
        else:
            self.datatype = datatype

        # Item, Property and MediaInfo specific
        self.labels: Labels = labels or Labels()
        self.descriptions: Descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    @property
    def datatype(self) -> Optional[str]:
        return self.__datatype

    @datatype.setter
    def datatype(self, value: Optional[str]):
        self.__datatype = value

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

    def new(self, **kwargs: Any) -> PropertyEntity:
        return PropertyEntity(api=self.api, **kwargs)

    def get(self, entity_id: Union[str, int], **kwargs: Any) -> PropertyEntity:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?P?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid property ID ({entity_id}), format must be 'P[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Property ID must be greater than 0")

        entity_id = f'P{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return PropertyEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> Dict[str, Union[str, Dict]]:
        return {
            'datatype': str(self.datatype),
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super().get_json()
        }

    def from_json(self, json_data: Dict[str, Any]) -> PropertyEntity:
        super().from_json(json_data=json_data)

        if 'datatype' in json_data:  # TODO: 1.35 compatibility
            self.datatype = json_data['datatype']
        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.aliases = Aliases().from_json(json_data['aliases'])

        return self

    def write(self, **kwargs: Any) -> PropertyEntity:
        """
        Write the PropertyEntity data to the Wikibase instance and return the PropertyEntity object returned by the instance.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: Clear the existing entity before updating
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: an PropertyEntity of the response from the instance
        """
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
