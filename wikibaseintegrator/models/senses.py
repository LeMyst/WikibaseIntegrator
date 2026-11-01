from __future__ import annotations

from collections.abc import Iterator
from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.glosses import Glosses  # pylint: disable=unused-import  # Re-exported: Sense and Glosses used to be defined in this module
from wikibaseintegrator.models.sense import Sense
from wikibaseintegrator.wbi_enums import ActionIfExists


class Senses(BaseModel):
    def __init__(self) -> None:
        self.senses: list[Sense] = []

    def get(self, id: str) -> Sense | None:
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    # TODO: implement action_if_exists
    # action_if_exists is accepted for symmetry with Claims.add() but not implemented yet
    # pylint: disable-next=unused-argument
    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        self.senses.append(sense)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for sense in json_data:
            self.add(sense=Sense().from_json(sense))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for sense in self.senses:
            # A new sense removed before being written is left out, like a removed new claim: there is nothing to remove
            if sense.removed and not sense.id:
                continue
            json_data.append(sense.get_json())

        return json_data

    def __iter__(self) -> Iterator[Sense]:
        return iter(self.senses)

    def __len__(self) -> int:
        return len(self.senses)
