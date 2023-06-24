from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snaks import Snak, Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claims import Claim


class References(BaseModel):
    def __init__(self) -> None:
        self.references: list[Reference] = []

    @property
    def references(self) -> list[Reference]:
        return self.__references

    @references.setter
    def references(self, value: list[Reference]):
        self.__references = value

    def get(self, hash: str | None = None) -> Reference | None:
        for reference in self.references:
            if reference.hash == hash:
                return reference
        return None

    # TODO: implement action_if_exists
    def add(self, reference: Reference | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> References:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(reference, Claim):
            reference = Reference(snaks=Snaks().add(Snak().from_json(reference.get_json()['mainsnak'])))

        if reference is not None:
            assert isinstance(reference, Reference)

            if reference not in self.references:
                self.references.append(reference)

        return self

    def from_json(self, json_data: list[dict]) -> References:
        for reference in json_data:
            self.add(reference=Reference().from_json(reference))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for reference in self.references:
            json_data.append(reference.get_json())
        return json_data

    def remove(self, reference_to_remove: Claim | Reference) -> bool:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(reference_to_remove, Claim):
            reference_to_remove = Reference(snaks=Snaks().add(Snak().from_json(reference_to_remove.get_json()['mainsnak'])))

        assert isinstance(reference_to_remove, Reference)

        for reference in self.references:
            if reference == reference_to_remove:
                self.references.remove(reference)
                return True

        return False

    def clear(self) -> References:
        self.references = []
        return self

    def __iter__(self):
        return iter(self.references)

    def __len__(self):
        return len(self.references)


class Reference(BaseModel):
    def __init__(self, snaks: Snaks | None = None, snaks_order: list | None = None):
        self.hash = None
        self.snaks = snaks or Snaks()
        self.snaks_order = snaks_order or []

    @property
    def hash(self):
        return self.__hash

    @hash.setter
    def hash(self, value):
        self.__hash = value

    @property
    def snaks(self):
        return self.__snaks

    @snaks.setter
    def snaks(self, value):
        self.__snaks = value

    @property
    def snaks_order(self):
        return self.__snaks_order

    @snaks_order.setter
    def snaks_order(self, value):
        self.__snaks_order = value

    # TODO: implement action_if_exists
    def add(self, snak: Snak | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Reference:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(snak, Claim):
            snak = Snak().from_json(snak.get_json()['mainsnak'])

        if snak is not None:
            assert isinstance(snak, Snak)

        self.snaks.add(snak)

        return self

    def from_json(self, json_data: dict[str, Any]) -> Reference:
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
