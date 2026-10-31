from __future__ import annotations

from typing import Self

from wikibaseintegrator.models.alias import Alias
from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class Aliases(BaseModel):
    def __init__(self, language: str | None = None, value: str | None = None) -> None:
        self.aliases: dict[str, list[Alias]] = {}

        if language is not None:
            self.set(language=language, values=value)

    @property
    def aliases(self) -> dict[str, list[Alias]]:
        return self.__aliases

    @aliases.setter
    def aliases(self, value: dict[str, list[Alias]]) -> None:
        self.__aliases = value

    def get(self, language: str | None = None) -> list[Alias] | None:
        if language is None:
            # The aliases of every language, in a flat list
            return [item for sublist in self.aliases.values() for item in sublist]

        if language in self.aliases:
            return self.aliases[language]

        return None

    def add(self, language: str | None = None, values: str | list[str] | None = None) -> Self:
        """
        Add one or more aliases to a language, keeping the existing ones. An alias already present is left untouched,
        unless it was marked for removal, in which case it is kept instead.

        :param language: The language of the aliases. Use the default language in wbi_config if none specified.
        :param values: An alias or a list of aliases to add. Empty values are ignored.
        :return: The current Aliases object
        """
        language = str(language or config['DEFAULT_LANGUAGE'])

        if values is None:
            return self

        if isinstance(values, str):
            values = [values]
        elif not isinstance(values, list):
            raise TypeError(f"value must be a str or list of strings, got '{type(values)}'")

        aliases = self.aliases.setdefault(language, [])
        for value in values:
            if not value:
                continue

            existing_alias = next((alias for alias in aliases if alias == value), None)
            if existing_alias is None:
                aliases.append(Alias(language, value))
            else:
                existing_alias.removed = False

        return self

    def set(self, language: str | None = None, values: str | list | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Self:
        language = str(language or config['DEFAULT_LANGUAGE'])
        assert action_if_exists in ActionIfExists

        assert language is not None

        if language not in self.aliases:
            self.aliases[language] = []

        if values is None or values == '':
            if action_if_exists != ActionIfExists.KEEP:
                for alias in self.aliases[language]:
                    alias.remove()
            return self

        if isinstance(values, str):
            values = [values]
        elif values is not None and not isinstance(values, list):
            raise TypeError(f"value must be a str or list of strings, got '{type(values)}'")

        if action_if_exists == ActionIfExists.APPEND_OR_REPLACE:
            return self.add(language=language, values=values)

        if action_if_exists == ActionIfExists.REPLACE_ALL:
            aliases = []
            for value in values:
                alias = Alias(language, value)
                aliases.append(alias)
            self.aliases[language] = aliases
        elif action_if_exists == ActionIfExists.KEEP:
            if not self.aliases[language]:
                self.aliases[language].extend(Alias(language, value) for value in values)

        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for language, aliases in self.aliases.items():
            if language not in json_data:
                json_data[language] = []
            for alias in aliases:
                json_data[language].append(alias.get_json())
        return json_data

    def from_json(self, json_data: dict[str, list]) -> Self:
        for language in json_data:
            for alias in json_data[language]:
                self.set(alias['language'], alias['value'])

        return self

    def __len__(self) -> int:
        return len(self.aliases)
