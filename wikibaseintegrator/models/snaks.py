from __future__ import annotations

from typing import Dict, List

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snak import Snak


class Snaks(BaseModel):
    def __init__(self):
        self.snaks: Dict[str, List[Snak]] = {}

    def get(self, property: str) -> List[Snak]:
        return self.snaks[property]

    def add(self, snak: Snak) -> Snaks:
        property = snak.property_number

        if property not in self.snaks:
            self.snaks[property] = []

        self.snaks[property].append(snak)

        return self

    def from_json(self, json_data: Dict[str, List]) -> Snaks:
        for property in json_data:
            for snak in json_data[property]:
                self.add(snak=Snak().from_json(snak))

        return self

    def get_json(self) -> Dict[str, List]:
        json_data: Dict[str, List] = {}
        for property, snaks in self.snaks.items():
            if property not in json_data:
                json_data[property] = []
            for snak in snaks:
                json_data[property].append(snak.get_json())
        return json_data

    def __iter__(self):
        iterate = []
        for snak in self.snaks.values():
            iterate.extend(snak)
        return iter(iterate)

    def __len__(self):
        return len(self.snaks)
