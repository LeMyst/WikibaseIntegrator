from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class Qualifiers(BaseModel):
    def __init__(self) -> None:
        self.qualifiers: dict[str, list[Snak]] = {}

    @property
    def qualifiers(self):
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value: dict[str, list[Snak]]) -> None:
        assert isinstance(value, dict)
        self.__qualifiers = value

    def set(self, qualifiers: Qualifiers | list[Snak | Claim] | None) -> Self:
        if isinstance(qualifiers, list) or isinstance(qualifiers, Qualifiers):
            for qualifier in qualifiers:
                self.add(qualifier)
        elif qualifiers is None:
            self.qualifiers = {}
        else:
            self.qualifiers = qualifiers

        return self

    def get(self, property: str | int) -> list[Snak]:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property in self.qualifiers:
            return self.qualifiers[property]

        return []

    # TODO: implement action_if_exists
    # action_if_exists is accepted for symmetry with Claims.add() but not implemented yet
    # pylint: disable-next=unused-argument
    def add(self, qualifier: Snak | Claim, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        # Imported here because Claim holds Qualifiers, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        if qualifier is not None:
            assert isinstance(qualifier, Snak)

        property = qualifier.property_number

        if property not in self.qualifiers:
            self.qualifiers[property] = []

        self.qualifiers[property].append(qualifier)

        return self

    def remove(self, qualifier: Snak | Claim) -> Self:
        """
        Remove a qualifier, given as a Snak or as a Claim of the same property and value. Nothing happens if it isn't there.

        :param qualifier: The qualifier to remove
        :return: This Qualifiers object
        """
        from wikibaseintegrator.models.claim import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        if qualifier is not None:
            assert isinstance(qualifier, Snak)

        # Removing a qualifier that isn't there does nothing, whether its property has other qualifiers or none
        qualifiers = self.qualifiers.get(qualifier.property_number)
        if qualifiers is None:
            return self

        if qualifier in qualifiers:
            qualifiers.remove(qualifier)

        if len(qualifiers) == 0:
            del self.qualifiers[qualifier.property_number]

        return self

    def clear(self, property: str | int | None = None) -> Self:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property is None:
            self.qualifiers = {}
        elif property in self.qualifiers:
            del self.qualifiers[property]
        return self

    def from_json(self, json_data: dict[str, list]) -> Self:
        for property in json_data:
            for snak in json_data[property]:
                self.add(qualifier=Snak().from_json(snak))
        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for property in self.qualifiers:
            if property not in json_data:
                json_data[property] = []

            for qualifier in self.qualifiers[property]:
                json_data[property].append(qualifier.get_json())
        return json_data

    def count(self) -> int:
        """
        Return the total number of individual qualifier snaks, across every property.

        Note: ``len(qualifiers)`` returns the number of distinct properties, while iterating yields the individual
        snaks. Use this method when you need the qualifier count.
        """
        return sum(len(snak_list) for snak_list in self.qualifiers.values())

    def __iter__(self) -> Iterator[Snak]:
        iterate = []
        for qualifier in self.qualifiers.values():
            iterate.extend(qualifier)
        return iter(iterate)

    def __len__(self) -> int:
        # Returns the number of distinct properties. See count() for the total number of individual snaks.
        return len(self.qualifiers)
