from __future__ import annotations

from collections.abc import Iterator
from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.form import Form
from wikibaseintegrator.models.representations import Representations  # pylint: disable=unused-import  # Re-exported: Form and Representations used to be defined in this module


class Forms(BaseModel):
    def __init__(self) -> None:
        self.forms: list[Form] = []

    @property
    def forms(self) -> list[Form]:
        return self.__forms

    @forms.setter
    def forms(self, value: list[Form]) -> None:
        self.__forms = value

    def get(self, id: str) -> Form | None:
        search = [x for x in self.__forms if x.id == id]
        if len(search) == 1:
            return search[0]
        elif len(search) > 1:
            raise ValueError('There is multiple form with the same id')

        return None

    def add(self, form: Form) -> Self:
        self.__forms.append(form)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for form in json_data:
            self.add(form=Form().from_json(form))

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for form in self.forms:
            json_data.append(form.get_json())

        return json_data

    def __iter__(self) -> Iterator[Form]:
        return iter(self.forms)

    def __len__(self) -> int:
        return len(self.forms)
