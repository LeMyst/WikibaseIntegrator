from __future__ import annotations

import json
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.glosses import Glosses
from wikibaseintegrator.models.language_values import LanguageValues


class Sense(BaseModel):
    def __init__(self, sense_id: str | None = None, glosses: Glosses | None = None, claims: Claims | None = None) -> None:
        self.id = sense_id
        self.glosses: LanguageValues = glosses or Glosses()
        self.claims = claims or Claims()
        self.removed = False

    def from_json(self, json_data: dict[str, Any]) -> Self:
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

    def remove(self) -> Self:
        self.removed = True
        return self

    def _content(self) -> str:
        # The id is assigned by the Wikibase instance, so two senses are considered equal when they hold the same content
        return json.dumps([self.glosses.get_json(), self.claims.get_json()], sort_keys=True)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sense):
            return NotImplemented

        return self._content() == other._content()

    def __hash__(self) -> int:
        # Based on the content, like __eq__: a Sense modified after being added to a set or used as a dict key won't be found anymore
        return hash(self._content())
