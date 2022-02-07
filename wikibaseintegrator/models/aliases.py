from __future__ import annotations

from typing import Dict, List, Optional, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.language_values import LanguageValue
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class Aliases(BaseModel):
    def __init__(self, language: str = None, value: str = None):
        self.aliases: Dict[str, str] = {}

        if language is not None:
            self.set(language=language, values=value)

    @property
    def aliases(self) -> Dict[str, List[Alias]]:
        return self.__aliases

    @aliases.setter
    def aliases(self, value: Dict[str, List[Alias]]):
        self.__aliases = value

    def get(self, language: str = None) -> Optional[List[Alias]]:
        if language is None:
            # TODO: Don't return a list of list, just a list
            return [item for sublist in self.aliases.values() for item in sublist]

        if language in self.aliases:
            return self.aliases[language]

        return None

    def set(self, language: str = None, values: Union[str, List] = None, action_if_exists: ActionIfExists = ActionIfExists.APPEND) -> Aliases:
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

        if action_if_exists == ActionIfExists.REPLACE:
            aliases = []
            for value in values:
                alias = Alias(language, value)
                aliases.append(alias)
            self.aliases[language] = aliases
        else:
            for value in values:
                alias = Alias(language, value)

                if action_if_exists == ActionIfExists.APPEND:
                    if alias not in self.aliases[language]:
                        self.aliases[language].append(alias)
                elif action_if_exists == ActionIfExists.KEEP:
                    if not self.aliases[language]:
                        self.aliases[language].append(alias)

        return self

    def get_json(self) -> Dict[str, List]:
        json_data: Dict[str, List] = {}
        for language, aliases in self.aliases.items():
            if language not in json_data:
                json_data[language] = []
            for alias in aliases:
                json_data[language].append(alias.get_json())
        return json_data

    def from_json(self, json_data: Dict[str, List]) -> Aliases:
        for language in json_data:
            for alias in json_data[language]:
                self.set(alias['language'], alias['value'])

        return self

    # def __contains__(self, item):
    #     all_aliases = [item for sublist in list(self.aliases.values()) for item in sublist]
    #     return item in list(map(lambda x: x.value, all_aliases))


class Alias(LanguageValue):
    pass
