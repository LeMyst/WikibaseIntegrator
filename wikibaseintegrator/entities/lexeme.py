from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.forms import Form, Forms
from wikibaseintegrator.models.lemmas import Lemmas
from wikibaseintegrator.models.senses import Sense, Senses
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import lexeme_add_form, lexeme_add_sense


class LexemeEntity(BaseEntity):
    ETYPE = 'lexeme'

    def __init__(self, lemmas: Lemmas | None = None, lexical_category: str | None = None, language: str | None = None, forms: Forms | None = None, senses: Senses | None = None,
                 **kwargs: Any):
        super().__init__(**kwargs)

        self.lemmas: Lemmas = lemmas or Lemmas()
        self.lexical_category: str | None = lexical_category
        self.language: str = str(language or config['DEFAULT_LEXEME_LANGUAGE'])
        self.forms: Forms = forms or Forms()
        self.senses: Senses = senses or Senses()

    @BaseEntity.id.setter  # type: ignore
    def id(self, value: None | str | int):
        if isinstance(value, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?L?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid lexeme ID ({value}), format must be 'L[0-9]+'")

            value = f'L{matches.group(1)}'
        elif isinstance(value, int):
            value = f'L{value}'
        elif value is None:
            pass
        else:
            raise ValueError(f"Invalid lexeme ID ({value}), format must be 'L[0-9]+'")

        BaseEntity.id.fset(self, value)  # type: ignore

    @property
    def lemmas(self) -> Lemmas:
        return self.__lemmas

    @lemmas.setter
    def lemmas(self, lemmas: Lemmas):
        if not isinstance(lemmas, Lemmas):
            raise TypeError
        self.__lemmas = lemmas

    @property
    def lexical_category(self) -> str | None:
        return self.__lexical_category

    @lexical_category.setter
    def lexical_category(self, lexical_category: str | None):
        self.__lexical_category = lexical_category

    @property
    def language(self) -> str:
        return self.__language

    @language.setter
    def language(self, language: str):
        if isinstance(language, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:|.+/entity/)?Q?([0-9]+)$')
            matches = pattern.match(language)

            if not matches:
                raise ValueError(f"Invalid lexeme language value ({language}), format must be 'Q[0-9]+'")

            language = f'Q{matches.group(1)}'
        elif isinstance(language, int):
            language = f'Q{language}'
        elif language is None:
            pass
        else:
            raise ValueError(f"Invalid lexeme language value ({language}), format must be 'Q[0-9]+'")

        self.__language = language

    @property
    def forms(self) -> Forms:
        return self.__forms

    @forms.setter
    def forms(self, forms: Forms):
        if not isinstance(forms, Forms):
            raise TypeError
        self.__forms = forms

    @property
    def senses(self) -> Senses:
        return self.__senses

    @senses.setter
    def senses(self, senses: Senses):
        if not isinstance(senses, Senses):
            raise TypeError
        self.__senses = senses

    def new(self, **kwargs: Any) -> LexemeEntity:
        return LexemeEntity(api=self.api, **kwargs)

    def get(self, entity_id: str | int, **kwargs: Any) -> LexemeEntity:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?L?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid lexeme ID ({entity_id}), format must be 'L[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Lexeme ID must be greater than 0")

        entity_id = f'L{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return LexemeEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> dict[str, str | dict]:
        json_data: dict = {
            'lemmas': self.lemmas.get_json(),
            'language': self.language,
            'forms': self.forms.get_json(),
            'senses': self.senses.get_json(),
            **super().get_json()
        }

        if self.lexical_category:
            json_data['lexicalCategory'] = self.lexical_category

        return json_data

    def from_json(self, json_data: dict[str, Any]) -> LexemeEntity:
        super().from_json(json_data=json_data)

        self.lemmas = Lemmas().from_json(json_data['lemmas'])
        self.lexical_category = str(json_data['lexicalCategory'])
        self.language = str(json_data['language'])
        self.forms = Forms().from_json(json_data['forms'])
        self.senses = Senses().from_json(json_data['senses'])

        return self

    def write(self, **kwargs: Any) -> LexemeEntity:
        """
        Write the LexemeEntity data to the Wikibase instance and return the LexemeEntity object returned by the instance.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: Clear the existing entity before updating
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: an LexemeEntity of the response from the instance
        """
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)

    def write_form(self, form: Form) -> str:
        if not self.id:
            raise Exception('You must set a Lexeme id before writing a Form.')
        return lexeme_add_form(lexeme_id=self.id, data=form.get_json())['form']['id']

    def write_forms(self) -> list[str]:
        ids: list = []
        for form in self.forms:
            ids.append(self.write_form(form))

        return ids

    def write_sense(self, sense: Sense) -> str:
        if not self.id:
            raise Exception('You must set a Lexeme id before writing a Sense.')
        return lexeme_add_sense(lexeme_id=self.id, data=sense.get_json())['sense']['id']

    def write_senses(self) -> list[str]:
        ids: list = []
        for sense in self.senses:
            ids.append(self.write_sense(sense))

        return ids
