from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Self

from wikibaseintegrator.models.basemodel import BaseModel, _add_with_action
from wikibaseintegrator.models.snak import Snak, _require_property_number
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class Qualifiers(BaseModel):
    def __init__(self) -> None:
        self.qualifiers: dict[str, list[Snak]] = {}

    @property
    def qualifiers(self) -> dict[str, list[Snak]]:
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value: dict[str, list[Snak]]) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"The qualifiers must be a dict, found {type(value)}")
        self.__qualifiers = value

    def set(self, qualifiers: Qualifiers | list[Snak | Claim] | None) -> Self:
        """
        Replace the qualifiers with the given ones, all of them, even the equal ones.

        :param qualifiers: The new qualifiers, as a Qualifiers object or a list of Snak or Claim objects. None removes them all.
        :return: This Qualifiers object
        """
        if isinstance(qualifiers, (list, Qualifiers)):
            # Copied first: the new qualifiers can be these qualifiers themselves
            new_qualifiers = list(qualifiers)
            self.qualifiers = {}
            for qualifier in new_qualifiers:
                self.add(qualifier, action_if_exists=ActionIfExists.FORCE_APPEND)
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

    def add(self, qualifier: Snak | Claim, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """
        Add a qualifier.

        :param qualifier: The qualifier, as a Snak or as a Claim whose main snak is taken. None adds nothing.
        :param action_if_exists: What to do when the qualifier already exists, like Claims.add(): two qualifiers are
            equal when they have the same property and value. Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE and MERGE_REFS_OR_APPEND: Add the new qualifier if no equal qualifier exists.
            FORCE_APPEND: Always add the new qualifier, even if an equal qualifier exists.
            KEEP: Add the new qualifier only if the property has no qualifier yet.
            REPLACE_ALL: Remove the qualifiers of the property not equal to the new one, then add it if it
            isn't there.
        :return: This Qualifiers object
        """
        # Imported here because Claim holds Qualifiers, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        # Adding no qualifier does nothing, like Reference.add() and References.add()
        if qualifier is None:
            return self

        if not isinstance(qualifier, Snak):
            raise TypeError(f"Expected a Snak or a Claim, found {type(qualifier)}")

        _add_with_action(self.qualifiers.setdefault(_require_property_number(qualifier), []), qualifier, action_if_exists)

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

        if not isinstance(qualifier, Snak):
            raise TypeError(f"Expected a Snak or a Claim, found {type(qualifier)}")

        # Removing a qualifier that isn't there does nothing, whether its property has other qualifiers or none, or it has no property
        property = qualifier.property_number
        qualifiers = self.qualifiers.get(property) if property is not None else None
        if property is None or qualifiers is None:
            return self

        if qualifier in qualifiers:
            qualifiers.remove(qualifier)

        if len(qualifiers) == 0:
            del self.qualifiers[property]

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
                # As they are on the instance
                self.add(qualifier=Snak().from_json(snak), action_if_exists=ActionIfExists.FORCE_APPEND)
        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for property, qualifiers in self.qualifiers.items():
            json_data[property] = [qualifier.get_json() for qualifier in qualifiers]
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
