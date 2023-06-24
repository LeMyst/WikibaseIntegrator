from __future__ import annotations

from typing import Any

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues
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
    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Senses:
        self.senses.append(sense)

        return self

    def from_json(self, json_data: list[dict]) -> Senses:
        for sense in json_data:
            self.add(sense=Sense().from_json(sense))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for sense in self.senses:
            json_data.append(sense.get_json())

        return json_data

    def __len__(self):
        return len(self.senses)


class Sense(BaseModel):
    def __init__(self, sense_id: str | None = None, glosses: Glosses | None = None, claims: Claims | None = None):
        self.id = sense_id
        self.glosses: LanguageValues = glosses or Glosses()
        self.claims = claims or Claims()
        self.removed = False

    def from_json(self, json_data: dict[str, Any]) -> Sense:
        self.id = json_data['id']
        self.glosses = Glosses().from_json(json_data['glosses'])
        self.claims = Claims().from_json(json_data['claims'])

        return self

    def get_json(self) -> dict[str, str | dict]:
        json_data: dict[str, str | dict] = {
            'id': str(self.id),
            'glosses': self.glosses.get_json(),
            'claims': self.claims.get_json()
        }

        if self.id is None:
            json_data['add'] = ''
            del json_data['id']

        if self.removed:
            json_data['remove'] = ''

        return json_data

    def remove(self) -> Sense:
        self.removed = True
        return self


class Glosses(LanguageValues):
    pass
