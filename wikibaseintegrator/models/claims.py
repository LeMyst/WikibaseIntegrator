from __future__ import annotations

from typing import Any, Dict, List, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.wbi_enums import ActionIfExists


class Claims(BaseModel):
    def __init__(self):
        self.claims: Dict[str, List[Claim]] = {}

    @property
    def claims(self) -> Dict[str, List[Claim]]:
        return self.__claims

    @claims.setter
    def claims(self, claims: Dict[str, List[Claim]]):
        self.__claims = claims

    def get(self, property: str) -> List[Claim]:
        return self.claims[property]

    def remove(self, property: str = None) -> None:
        if property in self.claims:
            for prop in self.claims[property]:
                if prop.id:
                    prop.remove()
                else:
                    self.claims[property].remove(prop)
            if len(self.claims[property]) == 0:
                del self.claims[property]

    def add(self, claims: Union[Claims, List[Claim], Claim], action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Claims:
        """

        :param claims: A Claim, list of Claim or just a Claims object to add to this Claims object.
        :param action_if_exists: Replace or append the statement. You can force an addition if the declaration already exists. Defaults to REPLACE_ALL.
            KEEP: The original claim will be kept and the new one will not be added (because there is already one with this property number)
            APPEND_OR_REPLACE: The new claim will be added only if the new one is different (by comparing values)
            FORCE_APPEND: The new claim will be added even if already exists
            REPLACE_ALL: The new claim will replace the old one
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

        return self

    def from_json(self, json_data: Dict[str, Any]) -> Claims:
        for property in json_data:
            for claim in json_data[property]:
                from wikibaseintegrator.datatypes import BaseDataType
                if 'datatype' in claim['mainsnak']:
                    data_type = [x for x in BaseDataType.subclasses if x.DTYPE == claim['mainsnak']['datatype']][0]
                else:
                    data_type = BaseDataType
                self.add(claims=data_type().from_json(claim), action_if_exists=ActionIfExists.FORCE_APPEND)

        return self

    def get_json(self) -> Dict[str, List]:
        json_data: Dict[str, List] = {}
        for property, claims in self.claims.items():
            if property not in json_data:
                json_data[property] = []
            for claim in claims:
                if not claim.removed or claim.id:
                    json_data[property].append(claim.get_json())
            if len(json_data[property]) == 0:
                del json_data[property]
        return json_data

    def __len__(self):
        return len(self.claims)

    def __iter__(self):
        iterate = []
        for claim in self.claims.values():
            iterate.extend(claim)
        return iter(iterate)
