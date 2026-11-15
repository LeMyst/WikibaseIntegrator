from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel, _add_with_action
from wikibaseintegrator.models.form import Form
from wikibaseintegrator.models.representations import Representations as _Representations
from wikibaseintegrator.wbi_enums import ActionIfExists


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

    def add(self, form: Form, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """
        Add a form to the lexeme.

        :param form: The form.
        :param action_if_exists: What to do when the form already exists, like Claims.add(): two forms are the
            same when they have the same id, or, when one of them has no id yet, the same content (see Form.__eq__()).
            Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE and MERGE_REFS_OR_APPEND: Add the new form if it isn't there. Otherwise, the new form
            replaces the one with the same id, or cancels the removal of the one with the same content.
            FORCE_APPEND: Always add the new form, even if it is already there.
            KEEP: Add the new form only if the lexeme has no form yet (the ones marked for removal don't count).
            REPLACE_ALL: Mark for removal the forms that aren't the new one, then add it like APPEND_OR_REPLACE.
        :return: This Forms object
        """
        _add_with_action(self.__forms, form, action_if_exists)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for form in json_data:
            # As they are on the instance
            self.add(form=Form().from_json(form), action_if_exists=ActionIfExists.FORCE_APPEND)

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

    def count(self) -> int:
        """Return the number of forms: the same as ``len()``."""
        return len(self)
