from __future__ import annotations

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.language_values import LanguageValue
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class Aliases(BaseModel):
    def __init__(self, language: str | None = None, value: str | None = None):
        self.aliases: dict[str, list[Alias]] = {}

        if language is not None:
            self.set(language=language, values=value)

    @property
    def aliases(self) -> dict[str, list[Alias]]:
        return self.__aliases

    @aliases.setter
    def aliases(self, value: dict[str, list[Alias]]):
        self.__aliases = value

    def get(self, language: str | None = None) -> list[Alias] | None:
        if language is None:
            # TODO: Don't return a list of list, just a list
            return [item for sublist in self.aliases.values() for item in sublist]

        if language in self.aliases:
            return self.aliases[language]

        return None

    def set(self, language: str | None = None, values: str | list | None = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> Aliases:
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

        if action_if_exists == ActionIfExists.REPLACE_ALL:
            aliases = []
            for value in values:
                alias = Alias(language, value)
                aliases.append(alias)
            self.aliases[language] = aliases
        else:
            for value in values:
                alias = Alias(language, value)

                if action_if_exists == ActionIfExists.APPEND_OR_REPLACE:
                    if alias not in self.aliases[language]:
                        self.aliases[language].append(alias)
                elif action_if_exists == ActionIfExists.KEEP:
                    if not self.aliases[language]:
                        self.aliases[language].append(alias)

        return self

    def get_json(self) -> dict[str, list]:
        json_data: dict[str, list] = {}
        for language, aliases in self.aliases.items():
            if language not in json_data:
                json_data[language] = []
            for alias in aliases:
                json_data[language].append(alias.get_json())
        return json_data

    def from_json(self, json_data: dict[str, list]) -> Aliases:
        for language in json_data:
            for alias in json_data[language]:
                self.set(alias['language'], alias['value'])

        return self

    # def __contains__(self, item):
    #     all_aliases = [item for sublist in list(self.aliases.values()) for item in sublist]
    #     return item in list(map(lambda x: x.value, all_aliases))


class Alias(LanguageValue):
    pass
