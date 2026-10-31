from __future__ import annotations

from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel


class LanguageValue(BaseModel):
    def __init__(self, language: str, value: str | None = None) -> None:
        self.language = language
        self.value = value
        self.removed = False

    @property
    def language(self) -> str:
        return self.__language

    @language.setter
    def language(self, value: str | None) -> None:
        if value is None:
            raise ValueError("language can't be None")

        if value == '':
            raise ValueError("language can't be empty")

        if not isinstance(value, str):
            raise ValueError("language must be a str")

        self.__language = value

    @property
    def value(self) -> str | None:
        """
        The value of the LanguageValue instance.
        :return: A string with the value of the LanguageValue instance.
        """
        return self.__value

    @value.setter
    def value(self, value: str | None) -> None:
        self.__value = value

    @property
    def removed(self) -> bool:
        return self.__removed

    @removed.setter
    def removed(self, value: bool) -> None:
        self.__removed = value

    def remove(self) -> Self:
        self.removed = True

        return self

    def from_json(self, json_data: dict[str, str]) -> Self:
        self.language = json_data['language']
        self.value = json_data['value']

        return self

    def get_json(self) -> dict[str, str | None]:
        json_data = {
            'language': self.language,
            'value': self.value
        }
        if self.removed:
            json_data['remove'] = ''
        return json_data

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in (self.value or '')

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LanguageValue):
            return self.value == other.value and self.language == other.language

        return self.value == other

    def __len__(self) -> int:
        return len(self.value or '')

    def __str__(self) -> str:
        return self.value or ''
