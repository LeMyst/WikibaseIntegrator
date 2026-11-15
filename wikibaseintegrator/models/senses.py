from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel, _add_with_action
from wikibaseintegrator.models.glosses import Glosses as _Glosses
from wikibaseintegrator.models.sense import Sense
from wikibaseintegrator.wbi_enums import ActionIfExists


def __getattr__(name: str) -> Any:
    # Sense and Glosses used to be defined in this module: Sense is still imported here, Glosses only until 1.0
    if name == 'Glosses':
        warnings.warn(f"Importing Glosses from {__name__} is deprecated and will be removed in WikibaseIntegrator 1.0, import it from wikibaseintegrator.models instead.",
                      DeprecationWarning, stacklevel=2)
        return _Glosses
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Senses(BaseModel):
    def __init__(self) -> None:
        self.senses: list[Sense] = []

    def get(self, id: str) -> Sense | None:
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    def add(self, sense: Sense, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        """
        Add a sense to the lexeme.

        :param sense: The sense.
        :param action_if_exists: What to do when the sense already exists, like Claims.add(): two senses are the
            same when they have the same id, or, when one of them has no id yet, the same content (see Sense.__eq__()).
            Defaults to APPEND_OR_REPLACE.
            APPEND_OR_REPLACE and MERGE_REFS_OR_APPEND: Add the new sense if it isn't there. Otherwise, the new sense
            replaces the one with the same id, or cancels the removal of the one with the same content.
            FORCE_APPEND: Always add the new sense, even if it is already there.
            KEEP: Add the new sense only if the lexeme has no sense yet (the ones marked for removal don't count).
            REPLACE_ALL: Mark for removal the senses that aren't the new one, then add it like APPEND_OR_REPLACE.
        :return: This Senses object
        """
        _add_with_action(self.senses, sense, action_if_exists)

        return self

    def from_json(self, json_data: list[dict]) -> Self:
        for sense in json_data:
            # As they are on the instance
            self.add(sense=Sense().from_json(sense), action_if_exists=ActionIfExists.FORCE_APPEND)

        return self

    def get_json(self) -> list[dict]:
        json_data: list[dict] = []
        for sense in self.senses:
            # A new sense removed before being written is left out, like a removed new claim: there is nothing to remove
            if sense.removed and not sense.id:
                continue
            json_data.append(sense.get_json())

        return json_data

    def __iter__(self) -> Iterator[Sense]:
        return iter(self.senses)

    def __len__(self) -> int:
        return len(self.senses)
