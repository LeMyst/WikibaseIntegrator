from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Self

from wikibaseintegrator.models.basemodel import BaseModel, _add_with_action
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
    def references(self, value: list[Reference]) -> None:
        self.__references = value

    def get(self, hash: str | None = None) -> Reference | None:
        for reference in self.references:
            if reference.hash == hash:
                return reference
        return None

    def add(self, reference: Reference | Claim | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """
        Add a reference.

        :param reference: The reference, as a Reference or as a Claim whose main snak is the only snak of a new
            reference. None adds nothing.
        :param action_if_exists: What to do when the reference already exists, like Claims.add(): two references are
            equal when they hold the same snaks (the hash isn't compared). Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE and MERGE_REFS_OR_APPEND: Add the new reference if no equal reference exists.
            FORCE_APPEND: Always add the new reference, even if an equal reference exists.
            KEEP: Add the new reference only if the claim has no reference yet.
            REPLACE_ALL: Remove the references not equal to the new one, then add it if it isn't there.
        :return: This References object
        """
        # Imported here because Claim holds References, which would make a circular import at module level
        from wikibaseintegrator.models.claim import Claim
        if isinstance(reference, Claim):

            if reference.qualifiers:
                log.warning("WARNING: It is not possible to use a qualifier in a reference, it will be ignored.")

            if reference.references:
                log.warning("WARNING: It is not possible to use a reference in a reference, it will be ignored.")

            reference = Reference(snaks=Snaks().add(Snak().from_json(reference.get_json()['mainsnak'])))

        if reference is not None:
            if not isinstance(reference, Reference):
                raise TypeError(f"Expected a Reference or a Claim, found {type(reference)}")

            _add_with_action(self.references, reference, action_if_exists)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for reference in json_data:
            # As they are on the instance
            self.add(reference=Reference().from_json(reference), action_if_exists=ActionIfExists.FORCE_APPEND)

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

        if not isinstance(reference_to_remove, Reference):
            raise TypeError(f"Expected a Reference or a Claim, found {type(reference_to_remove)}")

        for reference in self.references:
            if reference == reference_to_remove:
                self.references.remove(reference)
                return True

        return False

    def clear(self) -> Self:
        self.references = []
        return self

    def __iter__(self) -> Iterator[Reference]:
        return iter(self.references)

    def __len__(self) -> int:
        return len(self.references)

    def count(self) -> int:
        """Return the number of references: the same as ``len()``."""
        return len(self)
