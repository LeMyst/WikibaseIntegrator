from __future__ import annotations

from typing import Dict, Optional

from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class LanguageValues:
    def __init__(self):
        self.values = {}

    @property
    def values(self):
        return self.__values

    @values.setter
    def values(self, value):
        self.__values = value

    def add(self, language_value: LanguageValue) -> LanguageValues:
        assert isinstance(language_value, LanguageValue)

        if language_value.value:
            self.values[language_value.language] = language_value

        return self

    def get(self, language: str = None) -> Optional[LanguageValue]:
        language = str(language or config['DEFAULT_LANGUAGE'])
        if language in self.values:
            return self.values[language]

        return None

    def set(self, language: str = None, value: str = None, action_if_exists=ActionIfExists.REPLACE):
        language = str(language or config['DEFAULT_LANGUAGE'])
        assert action_if_exists in [ActionIfExists.REPLACE, ActionIfExists.KEEP]

        # Remove value if None
        if value is None and language in self.values:
            self.values[language].remove()
            return None

        if action_if_exists == ActionIfExists.REPLACE or self.get(language=language) is None:
            language_value = LanguageValue(language, value)
            self.add(language_value)
            return language_value

        return self.get(language=language)

    def from_json(self, json_data: Dict[str, Dict]):
        for language_value in json_data:
            self.add(language_value=LanguageValue(language=json_data[language_value]['language']).from_json(json_data=json_data[language_value]))

        return self

    def get_json(self) -> Dict[str, Dict]:
        json_data: Dict[str, Dict] = {}
        for value in self.values:
            json_data[value] = self.values[value].get_json()

        return json_data

    def __iter__(self):
        return iter(self.values.values())

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class LanguageValue:
    def __init__(self, language: str, value: str = None):
        self.language = language
        self.value = value
        self.removed = False

    @property
    def language(self):
        return self.__language

    @language.setter
    def language(self, value):
        if value is None:
            raise ValueError("language can't be None")

        if value == '':
            raise ValueError("language can't be empty")

        if not isinstance(value, str):
            raise ValueError("language must be a str")

        self.__language = value

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = value

    @property
    def removed(self):
        return self.__removed

    @removed.setter
    def removed(self, value):
        self.__removed = value

    def remove(self) -> LanguageValue:
        self.removed = True

        return self

    def from_json(self, json_data: Dict[str, str]) -> LanguageValue:
        self.language = json_data['language']
        self.value = json_data['value']

        return self

    def get_json(self) -> Dict[str, str]:
        json_data = {
            'language': self.language,
            'value': self.value
        }
        if self.removed:
            json_data['remove'] = ''
        return json_data

    def __contains__(self, item):
        return item in self.value

    def __eq__(self, other):
        if isinstance(other, LanguageValue):
            return self.value == other.value and self.language == other.language

        return self.value == other

    def __len__(self):
        return len(self.value)

    def __str__(self):
        return self.value

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
