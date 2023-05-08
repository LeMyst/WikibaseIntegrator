from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snaks import Snak
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claims import Claim


class Qualifiers(BaseModel):
    def __init__(self) -> None:
        self.qualifiers: Dict[str, List[Snak]] = {}

    @property
    def qualifiers(self):
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value):
        assert isinstance(value, dict)
        self.__qualifiers = value

    def set(self, qualifiers: Union[Qualifiers, List[Union[Snak, Claim]], None]) -> Qualifiers:
        if isinstance(qualifiers, list) or isinstance(qualifiers, Qualifiers):
            for qualifier in qualifiers:
                self.add(qualifier)
        elif qualifiers is None:
            self.qualifiers = {}
        else:
            self.qualifiers = qualifiers

        return self

    def get(self, property: Union[str, int]) -> List[Snak]:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property in self.qualifiers:
            return self.qualifiers[property]

        return []

    # TODO: implement action_if_exists
    def add(self, qualifier: Union[Snak, Claim], action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Qualifiers:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        if qualifier is not None:
            assert isinstance(qualifier, Snak)

        property = qualifier.property_number

        if property not in self.qualifiers:
            self.qualifiers[property] = []

        self.qualifiers[property].append(qualifier)

        return self

    def remove(self, qualifier: Union[Snak, Claim]) -> Qualifiers:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        if qualifier is not None:
            assert isinstance(qualifier, Snak)

        self.qualifiers[qualifier.property_number].remove(qualifier)

        if len(self.qualifiers[qualifier.property_number]) == 0:
            del self.qualifiers[qualifier.property_number]

        return self

    def clear(self, property: Optional[Union[str, int]] = None) -> Qualifiers:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property is None:
            self.qualifiers = {}
        elif property in self.qualifiers:
            del self.qualifiers[property]
        return self

    def from_json(self, json_data: Dict[str, List]) -> Qualifiers:
        for property in json_data:
            for snak in json_data[property]:
                self.add(qualifier=Snak().from_json(snak))
        return self

    def get_json(self) -> Dict[str, List]:
        json_data: Dict[str, List] = {}
        for property in self.qualifiers:
            if property not in json_data:
                json_data[property] = []

            for qualifier in self.qualifiers[property]:
                json_data[property].append(qualifier.get_json())
        return json_data

    def __iter__(self):
        iterate = []
        for qualifier in self.qualifiers.values():
            iterate.extend(qualifier)
        return iter(iterate)

    def __len__(self):
        return len(self.qualifiers)
