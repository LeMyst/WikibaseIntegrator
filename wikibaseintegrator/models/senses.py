from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues
from wikibaseintegrator.wbi_enums import ActionIfExists


class Senses(BaseModel):
    def __init__(self):
        self.senses = []

    def get(self, id: str) -> Optional[Sense]:
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    # TODO: implement action_if_exists
    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.REPLACE) -> Senses:
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


class Sense(BaseModel):
    def __init__(self, sense_id: str = None, glosses: Glosses = None, claims: Claims = None):
        self.id = sense_id
        self.glosses: LanguageValues = glosses or Glosses()
        self.claims = claims or Claims()
        self.removed = False

    def from_json(self, json_data: Dict[str, Any]) -> Sense:
        self.id = json_data['id']
        self.glosses = Glosses().from_json(json_data['glosses'])
        self.claims = Claims().from_json(json_data['claims'])

        return self

    def get_json(self) -> Dict[str, Union[str, Dict]]:
        json_data: Dict[str, Union[str, Dict]] = {
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
