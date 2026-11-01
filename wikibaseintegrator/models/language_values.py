from __future__ import annotations

from collections.abc import Iterator
from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.language_value import LanguageValue
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class LanguageValues(BaseModel):
    def __init__(self) -> None:
        self.values: dict[str, LanguageValue] = {}

    @property
    def values(self) -> dict[str, LanguageValue]:
        """
        A dict of LanguageValue with the language as key.
        """
        return self.__values

    @values.setter
    def values(self, value: dict[str, LanguageValue]) -> None:
        self.__values = value

    def add(self, language_value: LanguageValue) -> Self:
        """
        Add a LanguageValue object to the list

        :param language_value: A LanguageValue object
        :return: The current LanguageValues object
        """
        assert isinstance(language_value, LanguageValue)

        if language_value.value:
            self.values[language_value.language] = language_value

        return self

    def get(self, language: str | None = None) -> LanguageValue | None:
        """
        Get a LanguageValue object with the specified language. Use the default language in wbi_config if none specified.

        :param language: The requested language.
        :return: The related LanguageValue object or None if none found.
        """
        language = str(language or config['DEFAULT_LANGUAGE'])
        if language in self.values:
            return self.values[language]

        return None

    def set(self, language: str | None = None, value: str | None = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> LanguageValue | None:
        """
        Create or update the specified language with the valued passed in arguments.

        :param language: The desired language.
        :param value: The desired value of the LanguageValue object. Use None to delete an existing LanguageValue object from the list.
        :param action_if_exists: The action if the LanguageValue object is already defined. Can be ActionIfExists.REPLACE_ALL (default) or ActionIfExists.KEEP.
        :return: The created or updated LanguageValue. None if there's no LanguageValue object with this language.
        """
        language = str(language or config['DEFAULT_LANGUAGE'])
        assert action_if_exists in [ActionIfExists.REPLACE_ALL, ActionIfExists.KEEP]

        # Remove value if None
        if value is None:
            if language in self.values:
                self.values[language].remove()
            return None

        # A removed value doesn't count as present for KEEP
        existing = self.get(language=language)
        if action_if_exists == ActionIfExists.REPLACE_ALL or existing is None or existing.removed:
            language_value = LanguageValue(language, value)
            self.add(language_value)
            return language_value

        return self.get(language=language)

    def from_json(self, json_data: dict[str, dict]) -> Self:
        """
        Create a new LanguageValues object from a JSON/dict object.

        :param json_data: A dict object who use the same format as Wikibase.
        :return: The newly created or updated object.
        """
        for language_value in json_data:
            self.add(language_value=LanguageValue(language=json_data[language_value]['language']).from_json(json_data=json_data[language_value]))

        return self

    def get_json(self) -> dict[str, dict]:
        """
        Get a formatted dict who respect the Wikibase format.

        :return: A dict using Wikibase format.
        """
        json_data: dict[str, dict] = {}
        for language, language_value in self.values.items():
            json_data[language] = language_value.get_json()

        return json_data

    def __contains__(self, language: str) -> bool:
        return language in self.values

    def __iter__(self) -> Iterator[LanguageValue]:
        return iter(self.values.values())

    def __len__(self) -> int:
        return len(self.values)
