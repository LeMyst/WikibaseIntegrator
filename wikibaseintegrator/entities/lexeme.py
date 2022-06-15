from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.forms import Forms
from wikibaseintegrator.models.lemmas import Lemmas
from wikibaseintegrator.models.senses import Senses
from wikibaseintegrator.wbi_config import config


class LexemeEntity(BaseEntity):
    ETYPE = 'lexeme'

    def __init__(self, lemmas: Lemmas = None, lexical_category: str = None, language: str = None, forms: Forms = None, senses: Senses = None, **kwargs: Any):
        super().__init__(**kwargs)

        self.lemmas: Lemmas = lemmas or Lemmas()
        self.lexical_category: Optional[str] = lexical_category
        self.language: str = str(language or config['DEFAULT_LEXEME_LANGUAGE'])
        self.forms: Forms = forms or Forms()
        self.senses: Senses = senses or Senses()

    @property
    def lemmas(self) -> Lemmas:
        return self.__lemmas

    @lemmas.setter
    def lemmas(self, lemmas: Lemmas):
        if not isinstance(lemmas, Lemmas):
            raise TypeError
        self.__lemmas = lemmas

    @property
    def lexical_category(self) -> Optional[str]:
        return self.__lexical_category

    @lexical_category.setter
    def lexical_category(self, lexical_category: Optional[str]):
        self.__lexical_category = lexical_category

    @property
    def language(self) -> str:
        return self.__language

    @language.setter
    def language(self, language: str):
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

    def get(self, entity_id: Union[str, int], **kwargs: Any) -> LexemeEntity:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^L?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid lexeme ID ({entity_id}), format must be 'L[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Lexeme ID must be greater than 0")

        entity_id = f'L{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return LexemeEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> Dict[str, Union[str, Dict]]:
        json_data: Dict = {
            'lemmas': self.lemmas.get_json(),
            'language': self.language,
            'forms': self.forms.get_json(),
            'senses': self.senses.get_json(),
            **super().get_json()
        }

        if self.lexical_category:
            json_data['lexicalCategory'] = self.lexical_category

        return json_data

    def from_json(self, json_data: Dict[str, Any]) -> LexemeEntity:
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
