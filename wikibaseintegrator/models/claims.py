from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_exceptions import UnknownDatatypeError

log = logging.getLogger(__name__)


class Claims(BaseModel):
    def __init__(self) -> None:
        self.claims: dict[str, list[Claim]] = {}

    @property
    def claims(self) -> dict[str, list[Claim]]:
        return self.__claims

    @claims.setter
    def claims(self, claims: dict[str, list[Claim]]) -> None:
        self.__claims = claims

    def get(self, property: str | int) -> list[Claim]:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property in self.claims:
            return self.claims[property]

        return []

    def remove(self, property: str | None = None) -> None:
        if property in self.claims:
            for prop in list(self.claims[property]):
                if prop.id:
                    prop.remove()
                else:
                    self.claims[property].remove(prop)
            if len(self.claims[property]) == 0:
                del self.claims[property]

    def add(self, claims: Claims | list[Claim] | Claim, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """

        :param claims: A Claim, list of Claim or just a Claims object to add to this Claims object.
        :param action_if_exists: What to do when the property already has claims. Two claims are equal when they have the
            same property, value and qualifiers (the rank and the references are not compared). Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE: Add the new claim if no equal claim exists. Otherwise, update the equal claim in place
            (same statement) instead of adding a duplicate: it takes the rank of the new claim if set (not normal), and
            its references if it has some (they replace the existing references). The other claims of the property are kept.
            MERGE_REFS_OR_APPEND: Add the new claim if no equal claim exists. Otherwise, add the references of the new
            claim missing from the equal claim. The other claims of the property are kept.
            FORCE_APPEND: Always add the new claim, even if an equal claim exists (duplicate statement).
            KEEP: Add the new claim only if the property has no claim yet, otherwise do nothing.
            REPLACE_ALL: Remove the claims of the property that are not equal to one of the new claims, then add the new
            claims not already present. The equal claims are kept as they are.
            A claim marked as removed (see Claim.remove()) doesn't count as existing for KEEP, and adding a claim equal to
            it cancels the removal, whatever the action, except FORCE_APPEND, which adds a new claim.
        :return: Return the updated Claims object.
        """

        if not isinstance(action_if_exists, ActionIfExists):
            raise ValueError(f'{action_if_exists} is not a valid action_if_exists value. Use the enum ActionIfExists')

        if isinstance(claims, Claim):
            claims = [claims]
        elif claims is None or ((not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims)):
            raise TypeError("claims must be an instance of Claim or Claims or a list of Claim")

        # This code is separated from the rest to avoid looping multiple over `self.claims`.
        if action_if_exists == ActionIfExists.REPLACE_ALL:
            for claim in claims:
                if claim is not None:
                    assert isinstance(claim, Claim)

                    property = claim.mainsnak.property_number
                    if property in self.claims:
                        for claim_to_remove in self.claims[property]:
                            if claim_to_remove not in claims:
                                claim_to_remove.remove()

        for claim in claims:
            if claim is not None:
                assert isinstance(claim, Claim)
                property = claim.mainsnak.property_number

                if property not in self.claims:
                    self.claims[property] = []

                if action_if_exists == ActionIfExists.KEEP:
                    # The removed claims will be deleted by the write: the property has no claim left
                    if all(existing_claim.removed for existing_claim in self.claims[property]):
                        self._append_or_replace(property=property, claim=claim)
                elif action_if_exists == ActionIfExists.FORCE_APPEND:
                    self.claims[property].append(claim)
                elif action_if_exists == ActionIfExists.APPEND_OR_REPLACE:
                    self._append_or_replace(property=property, claim=claim)
                elif action_if_exists == ActionIfExists.REPLACE_ALL:
                    equal_claim = self._find_equal(property=property, claim=claim)
                    if equal_claim is None:
                        self.claims[property].append(claim)
                    else:
                        equal_claim.removed = False
                elif action_if_exists == ActionIfExists.MERGE_REFS_OR_APPEND:
                    claim_exists = False
                    for existing_claim in self.claims[property]:
                        # Compare the main snaks (which also handles no-value/some-value snaks that have no
                        # datavalue) and the qualifiers to decide if the statement already exists.
                        if claim.mainsnak == existing_claim.mainsnak and claim.quals_equal(claim, existing_claim):
                            claim_exists = True
                            existing_claim.removed = False

                            # Check if current reference block is present on references
                            if not Claim.ref_present(newitem=claim, olditem=existing_claim):
                                for ref_to_add in claim.references:
                                    if ref_to_add not in existing_claim.references:
                                        existing_claim.references.add(ref_to_add)
                            break

                    # If the claim value does not exist, append it
                    if not claim_exists:
                        self.claims[property].append(claim)
        return self

    def _find_equal(self, property: str, claim: Claim) -> Claim | None:
        """
        Find the claim of the property equal to the given claim, preferring one that isn't marked as removed.
        """
        equal_claims = [existing_claim for existing_claim in self.claims[property] if existing_claim == claim]
        return next((equal_claim for equal_claim in equal_claims if not equal_claim.removed), equal_claims[0] if equal_claims else None)

    def _append_or_replace(self, property: str, claim: Claim) -> None:
        equal_claim = self._find_equal(property=property, claim=claim)
        if equal_claim is None:
            self.claims[property].append(claim)
        else:
            # Update the claim already present instead of adding a duplicate, and cancel its removal if any
            equal_claim.update(claim)
            equal_claim.removed = False

    def from_json(self, json_data: dict[str, Any]) -> Self:
        # Imported here because the datatypes subclass Claim, which would make a circular import at module level
        from wikibaseintegrator.datatypes import BaseDataType

        for property in json_data:
            for claim in json_data[property]:
                data_type: type[BaseDataType] = BaseDataType
                if 'datatype' in claim['mainsnak']:
                    try:
                        data_type = BaseDataType.get_datatype_class(claim['mainsnak']['datatype'])
                    except UnknownDatatypeError:
                        # Keep the claim as it is, so reading the entity doesn't fail and writing it back doesn't change it
                        log.warning("Unknown datatype '%s' for claim %s of property %s, kept as a BaseDataType", claim['mainsnak']['datatype'], claim.get('id'), property)
                self.add(claims=data_type().from_json(claim), action_if_exists=ActionIfExists.FORCE_APPEND)

        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for property, claims in self.claims.items():
            if property not in json_data:
                json_data[property] = []
            for claim in claims:
                if not claim.removed or claim.id:
                    json_data[property].append(claim.get_json())
            if len(json_data[property]) == 0:
                del json_data[property]
        return json_data

    def count(self) -> int:
        """
        Return the total number of individual claims, across every property.

        Note: ``len(claims)`` returns the number of distinct properties, while iterating (``for claim in claims``)
        yields the individual claims. Use this method when you need the claim count.
        """
        return sum(len(claim_list) for claim_list in self.claims.values())

    def __iter__(self) -> Iterator[Claim]:
        iterate = []
        for claim in self.claims.values():
            iterate.extend(claim)
        return iter(iterate)

    def __len__(self) -> int:
        # Returns the number of distinct properties. See count() for the total number of individual claims.
        return len(self.claims)
