from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.reference import Reference
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class References(BaseModel):
    def __init__(self):
        self.references: List[Reference] = []

    @property
    def references(self) -> List[Reference]:
        return self.__references

    @references.setter
    def references(self, value: List[Reference]):
        self.__references = value

    def get(self, hash: str = None) -> Optional[Reference]:
        for reference in self.references:
            if reference.hash == hash:
                return reference
        return None

    # TODO: implement action_if_exists
    def add(self, reference: Union[Reference, Claim] = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> References:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(reference, Claim):
            reference = Reference(snaks=Snaks().add(Snak().from_json(reference.get_json()['mainsnak'])))

        if reference is not None:
            assert isinstance(reference, Reference)

            if reference not in self.references:
                self.references.append(reference)

        return self

    def from_json(self, json_data: List[Dict]) -> References:
        for reference in json_data:
            self.add(reference=Reference().from_json(reference))

        return self

    def get_json(self) -> List[Dict]:
        json_data: List[Dict] = []
        for reference in self.references:
            json_data.append(reference.get_json())
        return json_data

    def remove(self, reference_to_remove: Union[Claim, Reference]) -> bool:
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
