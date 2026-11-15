from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.form import Form
from wikibaseintegrator.models.representations import Representations as _Representations


def __getattr__(name: str) -> Any:
    # Form and Representations used to be defined in this module: Form is still imported here, Representations only until 1.0
    if name == 'Representations':
        warnings.warn(f"Importing Representations from {__name__} is deprecated and will be removed in WikibaseIntegrator 1.0, import it from wikibaseintegrator.models instead.",
                      DeprecationWarning, stacklevel=2)
        return _Representations
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
        if len(search) > 1:
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
            # A new form removed before being written is left out, like a removed new claim: there is nothing to remove
            if form.removed and not form.id:
                continue
            json_data.append(form.get_json())

        return json_data

    def __iter__(self) -> Iterator[Form]:
        return iter(self.forms)

    def __len__(self) -> int:
        return len(self.forms)
