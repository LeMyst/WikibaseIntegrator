from __future__ import annotations

import re
from typing import Any, Dict, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models import LanguageValues
from wikibaseintegrator.models.forms import Forms
from wikibaseintegrator.models.lemmas import Lemmas
from wikibaseintegrator.models.senses import Senses
from wikibaseintegrator.wbi_config import config


class Lexeme(BaseEntity):
    ETYPE = 'lexeme'

    def __init__(self, lemmas: Lemmas = None, lexical_category: str = None, language: str = None, forms: Forms = None, senses: Senses = None, **kwargs: Any):
        super().__init__(**kwargs)

        self.lemmas: LanguageValues = lemmas or Lemmas()
        self.lexical_category = lexical_category
        self.language = str(language or config['DEFAULT_LEXEME_LANGUAGE'])
        self.forms = forms or Forms()
        self.senses = senses or Senses()

    def new(self, **kwargs: Any) -> Lexeme:
        return Lexeme(api=self.api, **kwargs)

    def get(self, entity_id: Union[str, int], **kwargs: Any) -> Lexeme:
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
        return Lexeme(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> Dict[str, Union[str, dict]]:
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

    def from_json(self, json_data: Dict[str, Any]) -> Lexeme:
        super().from_json(json_data=json_data)

        self.lemmas = Lemmas().from_json(json_data['lemmas'])
        self.lexical_category = str(json_data['lexicalCategory'])
        self.language = str(json_data['language'])
        self.forms = Forms().from_json(json_data['forms'])
        self.senses = Senses().from_json(json_data['senses'])

        return self

    def write(self, **kwargs: Any) -> Lexeme:
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
