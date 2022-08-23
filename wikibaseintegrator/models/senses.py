from __future__ import annotations

from typing import Dict, List, Optional

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.sense import Sense
from wikibaseintegrator.wbi_enums import ActionIfExists


class Senses(BaseModel):
    def __init__(self):
        self.senses: List[Sense] = []

    def get(self, id: str) -> Optional[Sense]:
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    # TODO: implement action_if_exists
    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Senses:
        self.senses.append(sense)

        return self

    def from_json(self, json_data: List[Dict]) -> Senses:
        for sense in json_data:
            self.add(sense=Sense().from_json(sense))

        return self

    def get_json(self) -> List[Dict]:
        json_data: List[Dict] = []
        for sense in self.senses:
            json_data.append(sense.get_json())

        return json_data
