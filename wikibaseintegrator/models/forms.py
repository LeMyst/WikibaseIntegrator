from __future__ import annotations

from typing import Any

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues


class Forms(BaseModel):
    def __init__(self) -> None:
        self.forms: list[Form] = []

    @property
    def forms(self) -> list:
        return self.__forms

    @forms.setter
    def forms(self, value):
        self.__forms = value

    def get(self, id: str) -> Form | None:
        search = [x for x in self.__forms if x.id == id]
        if len(search) == 1:
            return search[0]
        elif len(search) > 1:
            raise ValueError('There is multiple form with the same id')

        return None

    def add(self, form: Form) -> Forms:
        self.__forms.append(form)

        return self

    def from_json(self, json_data: list[dict]) -> Forms:
        for form in json_data:
            self.add(form=Form().from_json(form))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for form in self.forms:
            json_data.append(form.get_json())

        return json_data

    def __iter__(self):
        return self.forms

    def __len__(self):
        return len(self.forms)


class Form(BaseModel):
    def __init__(self, form_id: str | None = None, representations: Representations | None = None, grammatical_features: str | int | list[str] | None = None, claims: Claims | None = None):
        self.id = form_id
        self.representations: Representations = representations or LanguageValues()
        self.grammatical_features = grammatical_features or []
        self.claims = claims or Claims()

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, value):
        self.__id = value

    @property
    def representations(self):
        return self.__representations

    @representations.setter
    def representations(self, value):
        self.__representations = value

    @property
    def grammatical_features(self):
        return self.__grammatical_features

    @grammatical_features.setter
    def grammatical_features(self, value: str | int | list[str]):
        if not hasattr(self, '__grammatical_features') or value is None:
            self.__grammatical_features = []

        if isinstance(value, int):
            self.__grammatical_features.append('Q' + str(value))
        elif isinstance(value, str):
            self.__grammatical_features.append(value)
        elif isinstance(value, list):
            self.__grammatical_features = value
        else:
            raise TypeError(f"value must be a str, an int or a list of strings, got '{type(value)}'")

    @property
    def claims(self):
        return self.__claims

    @claims.setter
    def claims(self, value):
        self.__claims = value

    def from_json(self, json_data: dict[str, Any]) -> Form:
        self.id = json_data['id']
        self.representations = Representations().from_json(json_data['representations'])
        self.grammatical_features = json_data['grammaticalFeatures']
        self.claims = Claims().from_json(json_data['claims'])

        return self

    def get_json(self) -> dict[str, str | dict | list]:
        json_data: dict[str, str | dict | list] = {
            'id': self.id,
            'representations': self.representations.get_json(),
            'grammaticalFeatures': self.grammatical_features,
            'claims': self.claims.get_json()
        }

        if self.id is None:
            json_data['add'] = ''
            del json_data['id']

        return json_data


class Representations(LanguageValues):
    pass
