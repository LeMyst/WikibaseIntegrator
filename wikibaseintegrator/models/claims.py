from __future__ import annotations

from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.wbi_enums import ActionIfExists


class Claims(BaseModel):
    def __init__(self) -> None:
        self.claims: dict[str, list[Claim]] = {}

    @property
    def claims(self) -> dict[str, list[Claim]]:
        return self.__claims

    @claims.setter
    def claims(self, claims: dict[str, list[Claim]]):
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
        :return: Return the updated Claims object.
        """

        if action_if_exists not in ActionIfExists:
            raise ValueError(f'{action_if_exists} is not a valid action_if_exists value. Use the enum ActionIfExists')

        if isinstance(claims, Claim):
            claims = [claims]
        elif claims is None or ((not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims)):
            raise TypeError("claims must be an instance of Claim or Claims or a list of Claim")

        # TODO: Don't replace if claim is the same
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
                    if len(self.claims[property]) == 0:
                        self.claims[property].append(claim)
                elif action_if_exists == ActionIfExists.FORCE_APPEND:
                    self.claims[property].append(claim)
                elif action_if_exists == ActionIfExists.APPEND_OR_REPLACE:
                    if claim not in self.claims[property]:
                        self.claims[property].append(claim)
                    else:
                        # Force update the claim if already present
                        self.claims[property][self.claims[property].index(claim)].update(claim)
                elif action_if_exists == ActionIfExists.REPLACE_ALL:
                    if claim not in self.claims[property]:
                        self.claims[property].append(claim)
                elif action_if_exists == ActionIfExists.MERGE_REFS_OR_APPEND:
                    claim_exists = False
                    for existing_claim in self.claims[property]:
                        # Compare the main snaks (which also handles no-value/some-value snaks that have no
                        # datavalue) and the qualifiers to decide if the statement already exists.
                        if claim.mainsnak == existing_claim.mainsnak and claim.quals_equal(claim, existing_claim):
                            claim_exists = True

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

    def from_json(self, json_data: dict[str, Any]) -> Self:
        # Imported here because the datatypes subclass Claim, which would make a circular import at module level
        from wikibaseintegrator.datatypes import BaseDataType

        for property in json_data:
            for claim in json_data[property]:
                if 'datatype' in claim['mainsnak']:
                    data_type = [x for x in BaseDataType.subclasses if x.DTYPE == claim['mainsnak']['datatype']][0]
                else:
                    data_type = BaseDataType
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

    def __iter__(self):
        iterate = []
        for claim in self.claims.values():
            iterate.extend(claim)
        return iter(iterate)

    def __len__(self):
        # Returns the number of distinct properties. See count() for the total number of individual claims.
        return len(self.claims)
