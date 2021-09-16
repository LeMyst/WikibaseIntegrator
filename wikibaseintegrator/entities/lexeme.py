from __future__ import annotations

import re
from typing import Dict, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.forms import Forms
from wikibaseintegrator.models.lemmas import Lemmas
from wikibaseintegrator.models.senses import Senses
from wikibaseintegrator.wbi_config import config


class Lexeme(BaseEntity):
    ETYPE = 'lexeme'

    def __init__(self, api, lemmas=None, lexical_category=None, language=None, forms=None, senses=None, **kwargs):
        self.api = api

        super().__init__(api=self.api, **kwargs)

        self.lemmas = lemmas or Lemmas()
        self.lexical_category = lexical_category
        self.language = language or config['DEFAULT_LEXEME_LANGUAGE']
        self.forms = forms or Forms()
        self.senses = senses or Senses()

    def new(self, **kwargs) -> Lexeme:
        return Lexeme(self.api, **kwargs)

    def get(self, entity_id, **kwargs) -> Lexeme:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^L?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError("Invalid lexeme ID ({}), format must be 'L[0-9]+'".format(entity_id))

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("Lexeme ID must be greater than 0")

        entity_id = 'L{}'.format(entity_id)
        json_data = super().get(entity_id=entity_id, **kwargs)
        return Lexeme(self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_json(self) -> Dict[str, Union[str, Dict]]:
        json_data = {
            'lemmas': self.lemmas.get_json(),
            'lexicalCategory': self.lexical_category,
            'language': self.language,
            'forms': self.forms.get_json(),
            'senses': self.senses.get_json(),
            **super().get_json()
        }

        if self.lexical_category is None:
            del json_data['lexicalCategory']

        return json_data

    def from_json(self, json_data) -> Lexeme:
        super().from_json(json_data=json_data)

        self.lemmas = Lemmas().from_json(json_data['lemmas'])
        self.lexical_category = json_data['lexicalCategory']
        self.language = json_data['language']
        self.forms = Forms().from_json(json_data['forms'])
        self.senses = Senses().from_json(json_data['senses'])

        return self

    def write(self, **kwargs):
        if self.lexical_category is None:
            raise ValueError("lexical_category can't be None")

        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
