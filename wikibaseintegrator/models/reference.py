from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Self

from wikibaseintegrator.models.basemodel import BaseModel, _add_with_action
from wikibaseintegrator.models.snak import Snak, _copy_json, _require_property_number
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class Reference(BaseModel):
    def __init__(self, snaks: Snaks | None = None, snaks_order: list[str] | None = None) -> None:
        self.hash = None
        self.snaks = snaks if snaks is not None else Snaks()
        self.snaks_order = snaks_order or []

    @property
    def hash(self) -> str | None:
        return self.__hash

    @hash.setter
    def hash(self, value: str | None) -> None:
        self.__hash = value

    @property
    def snaks(self) -> Snaks:
        return self.__snaks

    @snaks.setter
    def snaks(self, value: Snaks) -> None:
        self.__snaks = value

    @property
    def snaks_order(self) -> list[str]:
        return self.__snaks_order

    @snaks_order.setter
    def snaks_order(self, value: list[str]) -> None:
        self.__snaks_order = value

    def add(self, snak: Snak | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """
        Add a snak to the reference.

        :param snak: The snak, as a Snak or as a Claim whose main snak is taken. None adds nothing.
        :param action_if_exists: What to do when the snak already exists, like Claims.add(): two snaks are
            equal when they have the same property and value. Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE and MERGE_REFS_OR_APPEND: Add the new snak if no equal snak exists.
            FORCE_APPEND: Always add the new snak, even if an equal snak exists.
            KEEP: Add the new snak only if the property has no snak yet.
            REPLACE_ALL: Remove the snaks of the property not equal to the new one, then add it if it isn't
            there.
        :return: This Reference object
        """
        # Imported here because Claim holds References, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(snak, Claim):
            snak = Snak().from_json(_copy_json(snak.mainsnak))

        if snak is not None:
            if not isinstance(snak, Snak):
                raise TypeError(f"Expected a Snak or a Claim, found {type(snak)}")
            _add_with_action(self.snaks.snaks.setdefault(_require_property_number(snak), []), snak, action_if_exists)

        return self

    def from_json(self, json_data: dict[str, Any]) -> Self:
        self.hash = json_data['hash']
        self.snaks = Snaks().from_json(json_data['snaks'])
        self.snaks_order = json_data['snaks-order']

        return self

    def get_json(self) -> dict[str, dict | list]:
        json_data: dict[str, dict | list] = {
            'snaks': self.snaks.get_json(),
            'snaks-order': self.snaks_order
        }
        return json_data

    def __iter__(self) -> Iterator[Snak]:
        return iter(self.snaks)

    def __len__(self) -> int:
        # The snaks, like the iteration: not the properties
        return len(self.snaks)

    def count(self) -> int:
        """Return the number of snaks of the reference, across every property: the same as ``len()``."""
        return len(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Reference):
            return NotImplemented

        # The hash is only known server-side, so two references are considered equal when they hold the same snaks, compared
        # as Snak (not as JSON) to ignore a missing datatype like Snak.__eq__
        return self.snaks == other.snaks
