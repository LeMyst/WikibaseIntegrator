from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.reference import Reference
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim

log = logging.getLogger(__name__)


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
    # action_if_exists is accepted for symmetry with Claims.add() but not implemented yet
    # pylint: disable-next=unused-argument
    def add(self, reference: Reference | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        # Imported here because Claim holds References, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(reference, Claim):

            if reference.qualifiers:
                log.warning("WARNING: It is not possible to use a qualifier in a reference, it will be ignored.")

            if reference.references:
                log.warning("WARNING: It is not possible to use a reference in a reference, it will be ignored.")

            reference = Reference(snaks=Snaks().add(Snak().from_json(reference.get_json()['mainsnak'])))

        if reference is not None:
            assert isinstance(reference, Reference)

            if reference not in self.references:
                self.references.append(reference)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for reference in json_data:
            self.add(reference=Reference().from_json(reference))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for reference in self.references:
            json_data.append(reference.get_json())
        return json_data

    def remove(self, reference_to_remove: Claim | Reference) -> bool:
        from wikibaseintegrator.models.claim import Claim
        if isinstance(reference_to_remove, Claim):
            reference_to_remove = Reference(snaks=Snaks().add(Snak().from_json(reference_to_remove.get_json()['mainsnak'])))

        assert isinstance(reference_to_remove, Reference)

        for reference in self.references:
            if reference == reference_to_remove:
                self.references.remove(reference)
                return True

        return False

    def clear(self) -> Self:
        self.references = []
        return self

    def __iter__(self):
        return iter(self.references)

    def __len__(self):
        return len(self.references)
