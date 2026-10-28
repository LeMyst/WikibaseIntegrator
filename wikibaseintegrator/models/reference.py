from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class Reference(BaseModel):
    def __init__(self, snaks: Snaks | None = None, snaks_order: list[str] | None = None):
        self.hash = None
        self.snaks = snaks or Snaks()
        self.snaks_order = snaks_order or []

    @property
    def hash(self) -> str | None:
        return self.__hash

    @hash.setter
    def hash(self, value: str | None):
        self.__hash = value

    @property
    def snaks(self) -> Snaks:
        return self.__snaks

    @snaks.setter
    def snaks(self, value: Snaks):
        self.__snaks = value

    @property
    def snaks_order(self) -> list[str]:
        return self.__snaks_order

    @snaks_order.setter
    def snaks_order(self, value: list[str]):
        self.__snaks_order = value

    # TODO: implement action_if_exists
    def add(self, snak: Snak | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        # Imported here because Claim holds References, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(snak, Claim):
            snak = Snak().from_json(snak.get_json()['mainsnak'])

        if snak is not None:
            assert isinstance(snak, Snak)
            self.snaks.add(snak)

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

    def __iter__(self):
        return iter(self.snaks)

    def __len__(self):
        return len(self.snaks)

    def __eq__(self, other):
        if not isinstance(other, Reference):
            return NotImplemented

        # The hash is only known server-side, so two references are considered equal when they hold the same snaks
        return self.snaks.get_json() == other.snaks.get_json()
