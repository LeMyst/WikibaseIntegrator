from __future__ import annotations

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
            json_data.append(sense.get_json())

        return json_data

    def __iter__(self):
        return iter(self.senses)

    def __len__(self):
        return len(self.senses)
