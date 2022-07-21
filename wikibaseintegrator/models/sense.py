from __future__ import annotations

from typing import Any, Dict, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.glosses import Glosses
from wikibaseintegrator.models.language_values import LanguageValues


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
