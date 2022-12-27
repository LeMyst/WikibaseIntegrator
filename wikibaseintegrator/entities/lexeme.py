from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.forms import Form, Forms
from wikibaseintegrator.models.lemmas import Lemmas
from wikibaseintegrator.models.senses import Sense, Senses
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import lexeme_add_form, lexeme_add_sense
from wikibaseintegrator.wbi_login import _Login


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

        if 'lemmas' in json_data:
            self.lemmas = Lemmas().from_json(json_data['lemmas'])
        if 'lexicalCategory' in json_data:
            self.lexical_category = str(json_data['lexicalCategory'])
        if 'language' in json_data:
            self.language = str(json_data['language'])
        if 'forms' in json_data:
            self.forms = Forms().from_json(json_data['forms'])
        if 'senses' in json_data:
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

    def write_form(self, form: Form, login: _Login | None = None, allow_anonymous: bool = False, is_bot: bool | None = None, **kwargs: Any) -> str:
        """
        Add a single Form to the Lexeme with the wbladdform action.

        Contrary to write(), only the Form is sent to the Wikibase instance, the rest of the Lexeme is left untouched.

        :param form: The Form to add. It must be a new Form, without an id.
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for lexeme_add_form and Python requests
        :return: The id of the newly created Form, e.g. L10-F2
        """
        if not self.id:
            raise ValueError('You must set a Lexeme id before writing a Form.')

        if form.id:
            raise ValueError(f"The Form {form.id} already exists, adding it again would create a duplicate.")

        data = form.get_json()
        # 'add' is a marker used by wbeditentity, the wbladdform action doesn't expect it.
        data.pop('add', None)

        login = login or self.api.login
        is_bot = is_bot if is_bot is not None else self.api.is_bot

        form.id = lexeme_add_form(lexeme_id=self.id, data=data, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)['form']['id']

        return form.id

    def write_forms(self, **kwargs: Any) -> list[str]:
        """
        Add all the new Forms of the Lexeme, one wbladdform action per Form. The Forms already existing on the
        Wikibase instance are skipped.

        :param kwargs: Arguments passed to write_form()
        :return: The ids of the newly created Forms
        """
        return [self.write_form(form, **kwargs) for form in self.forms if not form.id]

    def write_sense(self, sense: Sense, login: _Login | None = None, allow_anonymous: bool = False, is_bot: bool | None = None, **kwargs: Any) -> str:
        """
        Add a single Sense to the Lexeme with the wbladdsense action.

        Contrary to write(), only the Sense is sent to the Wikibase instance, the rest of the Lexeme is left untouched.

        :param sense: The Sense to add. It must be a new Sense, without an id.
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for lexeme_add_sense and Python requests
        :return: The id of the newly created Sense, e.g. L10-S2
        """
        if not self.id:
            raise ValueError('You must set a Lexeme id before writing a Sense.')

        if sense.id:
            raise ValueError(f"The Sense {sense.id} already exists, adding it again would create a duplicate.")

        if sense.removed:
            raise ValueError('The Sense is marked as removed, it cannot be added.')

        data = sense.get_json()
        # 'add' is a marker used by wbeditentity, the wbladdsense action doesn't expect it.
        data.pop('add', None)

        login = login or self.api.login
        is_bot = is_bot if is_bot is not None else self.api.is_bot

        sense.id = lexeme_add_sense(lexeme_id=self.id, data=data, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)['sense']['id']

        return sense.id

    def write_senses(self, **kwargs: Any) -> list[str]:
        """
        Add all the new Senses of the Lexeme, one wbladdsense action per Sense. The Senses already existing on the
        Wikibase instance and the Senses marked as removed are skipped.

        :param kwargs: Arguments passed to write_sense()
        :return: The ids of the newly created Senses
        """
        return [self.write_sense(sense, **kwargs) for sense in self.senses if not sense.id and not sense.removed]
