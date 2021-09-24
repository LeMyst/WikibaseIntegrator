from __future__ import annotations

from typing import Dict, List, Union

from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues
from wikibaseintegrator.wbi_enums import ActionIfExists


class Senses:
    def __init__(self):
        self.senses = []

    def get(self, id: str):
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    # TODO: implement action_if_exists
    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.REPLACE) -> Senses:
        self.senses.append(sense)

        return self

    def from_json(self, json_data: List[Dict]):
        for sense in json_data:
            self.add(sense=Sense().from_json(sense))

        return self

    def get_json(self) -> List[Dict]:
        json_data: List[Dict] = []
        for sense in self.senses:
            json_data.append(sense.get_json())

        return json_data

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class Sense:
    def __init__(self, sense_id: str = None, glosses: Glosses = None, claims: Claims = None):
        self.id = sense_id
        self.glosses = glosses or Glosses()
        self.claims = claims or Claims()
        self.removed = False

    def from_json(self, json_data):
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

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class Glosses(LanguageValues):
    pass
