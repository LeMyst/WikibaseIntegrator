from __future__ import annotations

from typing import Dict, List

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.form import Form


class Forms(BaseModel):
    def __init__(self):
        self.forms: Dict[str, Form] = {}

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
