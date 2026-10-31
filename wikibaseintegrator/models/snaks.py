from __future__ import annotations

from collections.abc import Iterator
from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snak import Snak


class Snaks(BaseModel):
    def __init__(self) -> None:
        self.snaks: dict[str, list[Snak]] = {}

    def get(self, property: str | int) -> list[Snak]:
        if isinstance(property, int):
            property = 'P' + str(property)

        if property in self.snaks:
            return self.snaks[property]

        return []

    def add(self, snak: Snak) -> Self:
        property = snak.property_number

        if property not in self.snaks:
            self.snaks[property] = []

        self.snaks[property].append(snak)

        return self

    def from_json(self, json_data: dict[str, list]) -> Self:
        for property in json_data:
            for snak in json_data[property]:
                self.add(snak=Snak().from_json(snak))

        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for property, snaks in self.snaks.items():
            if property not in json_data:
                json_data[property] = []
            for snak in snaks:
                json_data[property].append(snak.get_json())
        return json_data

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Snaks):
            return NotImplemented

        return self.snaks == other.snaks

    def __iter__(self) -> Iterator[Snak]:
        iterate = []
        for snak in self.snaks.values():
            iterate.extend(snak)
        return iter(iterate)

    def __len__(self) -> int:
        return len(self.snaks)
