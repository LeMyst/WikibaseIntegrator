from __future__ import annotations

from typing import Any, Dict, List, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues


class Forms(BaseModel):
    def __init__(self):
        self.forms = {}

    @property
    def forms(self) -> Dict:
        return self.__forms

    @forms.setter
    def forms(self, value):
        self.__forms = value

    def get(self, id: str) -> Form:
        return self.forms[id]

    def add(self, form: Form) -> Forms:
        self.forms[form.id] = form

        return self

    def from_json(self, json_data: List[Dict]) -> Forms:
        for form in json_data:
            self.add(form=Form().from_json(form))

        return self

    def get_json(self) -> List[Dict]:
        json_data: List[Dict] = []
        for _, form in self.forms.items():
            json_data.append(form.get_json())

        return json_data


class Form(BaseModel):
    def __init__(self, form_id: str = None, representations: Representations = None, grammatical_features: Union[str, int, List[str]] = None, claims: Claims = None):
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
    def grammatical_features(self, value: Union[str, int, List[str]]):
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

    def from_json(self, json_data: Dict[str, Any]) -> Form:
        self.id = json_data['id']
        self.representations = Representations().from_json(json_data['representations'])
        self.grammatical_features = json_data['grammaticalFeatures']
        self.claims = Claims().from_json(json_data['claims'])

        return self

    def get_json(self) -> Dict[str, Union[str, Dict, List]]:
        json_data: Dict[str, Union[str, Dict, List]] = {
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
