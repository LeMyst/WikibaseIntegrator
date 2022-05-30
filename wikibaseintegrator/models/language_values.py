from __future__ import annotations

from typing import Dict, Optional

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class LanguageValues(BaseModel):
    def __init__(self):
        self.values = {}

    @property
    def values(self) -> Dict[str, LanguageValue]:
        """
        A dict of LanguageValue with the language as key.
        """
        return self.__values

    @values.setter
    def values(self, value):
        self.__values = value

    def add(self, language_value: LanguageValue) -> LanguageValues:
        """
        Add a LanguageValue object to the list

        :param language_value: A LanguageValue object
        :return: The current LanguageValues object
        """
        assert isinstance(language_value, LanguageValue)

        if language_value.value:
            self.values[language_value.language] = language_value

        return self

    def get(self, language: str = None) -> Optional[LanguageValue]:
        """
        Get a LanguageValue object with the specified language. Use the default language in wbi_config if none specified.

        :param language: The requested language.
        :return: The related LanguageValue object or None if none found.
        """
        language = str(language or config['DEFAULT_LANGUAGE'])
        if language in self.values:
            return self.values[language]

        return None

    def set(self, language: str = None, value: str = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE) -> Optional[LanguageValue]:
        """
        Create or update the specified language with the valued passed in arguments.

        :param language: The desired language.
        :param value: The desired value of the LanguageValue object. Use None to delete an existing LanguageValue object from the list.
        :param action_if_exists: The action if the LanguageValue object is already defined. Can be ActionIfExists.REPLACE (default) or ActionIfExists.KEEP.
        :return: The created or updated LanguageValue. None if there's no LanguageValue object with this language.
        """
        language = str(language or config['DEFAULT_LANGUAGE'])
        assert action_if_exists in [ActionIfExists.REPLACE, ActionIfExists.KEEP]

        # Remove value if None
        if value is None:
            if language in self.values:
                self.values[language].remove()
            return None

        if action_if_exists == ActionIfExists.REPLACE or self.get(language=language) is None:
            language_value = LanguageValue(language, value)
            self.add(language_value)
            return language_value

        return self.get(language=language)

    def from_json(self, json_data: Dict[str, Dict]) -> LanguageValues:
        """
        Create a new LanguageValues object from a JSON/dict object.

        :param json_data: A dict object who use the same format as Wikibase.
        :return: The newly created or updated object.
        """
        for language_value in json_data:
            self.add(language_value=LanguageValue(language=json_data[language_value]['language']).from_json(json_data=json_data[language_value]))

        return self

    def get_json(self) -> Dict[str, Dict]:
        """
        Get a formatted dict who respect the Wikibase format.

        :return: A dict using Wikibase format.
        """
        json_data: Dict[str, Dict] = {}
        for language, language_value in self.values.items():
            json_data[language] = language_value.get_json()

        return json_data

    def __contains__(self, language: str) -> bool:
        return language in self.values

    def __iter__(self):
        return iter(self.values.values())


class LanguageValue(BaseModel):
    def __init__(self, language: str, value: str = None):
        self.language = language
        self.value = value
        self.removed = False

    @property
    def language(self) -> str:
        return self.__language

    @language.setter
    def language(self, value: Optional[str]):
        if value is None:
            raise ValueError("language can't be None")

        if value == '':
            raise ValueError("language can't be empty")

        if not isinstance(value, str):
            raise ValueError("language must be a str")

        self.__language = value

    @property
    def value(self) -> Optional[str]:
        """
        The value of the LanguageValue instance.
        :return: A string with the value of the LanguageValue instance.
        """
        return self.__value

    @value.setter
    def value(self, value: Optional[str]):
        self.__value = value

    @property
    def removed(self) -> bool:
        return self.__removed

    @removed.setter
    def removed(self, value: bool):
        self.__removed = value

    def remove(self) -> LanguageValue:
        self.removed = True

        return self

    def from_json(self, json_data: Dict[str, str]) -> LanguageValue:
        self.language = json_data['language']
        self.value = json_data['value']

        return self

    def get_json(self) -> Dict[str, Optional[str]]:
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
