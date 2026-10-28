from __future__ import annotations

import json
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues
from wikibaseintegrator.models.representations import Representations


class Form(BaseModel):
    def __init__(self, form_id: str | None = None, representations: Representations | None = None, grammatical_features: str | int | list[str] | None = None, claims: Claims | None = None):
        self.id = form_id
        self.representations = representations or Representations()
        self.grammatical_features = grammatical_features or []
        self.claims = claims or Claims()

    @property
    def id(self) -> str | None:
        return self.__id

    @id.setter
    def id(self, value: str | None):
        self.__id = value

    @property
    def representations(self) -> LanguageValues:
        return self.__representations

    @representations.setter
    def representations(self, value: LanguageValues):
        self.__representations = value

    @property
    def grammatical_features(self) -> list[str]:
        return self.__grammatical_features

    @grammatical_features.setter
    def grammatical_features(self, value: str | int | list[str] | None):
        if value is None:
            self.__grammatical_features: list[str] = []
        elif isinstance(value, bool):
            # bool is a subclass of int, reject it explicitly
            raise TypeError(f"value must be a str, an int or a list of strings, got '{type(value)}'")
        elif isinstance(value, int):
            self.__grammatical_features = ['Q' + str(value)]
        elif isinstance(value, str):
            self.__grammatical_features = [value]
        elif isinstance(value, list):
            self.__grammatical_features = value
        else:
            raise TypeError(f"value must be a str, an int or a list of strings, got '{type(value)}'")

    @property
    def claims(self) -> Claims:
        return self.__claims

    @claims.setter
    def claims(self, value: Claims):
        self.__claims = value

    def from_json(self, json_data: dict[str, Any]) -> Self:
        self.id = json_data['id']
        self.representations = Representations().from_json(json_data['representations'])
        self.grammatical_features = json_data['grammaticalFeatures']
        self.claims = Claims().from_json(json_data['claims'])

        return self

    def get_json(self) -> dict[str, str | dict | list]:
        json_data: dict[str, str | dict | list] = {
            'id': str(self.id),
            'representations': self.representations.get_json(),
            'grammaticalFeatures': self.grammatical_features,
            'claims': self.claims.get_json()
        }

        if self.id is None:
            json_data['add'] = ''
            del json_data['id']

        return json_data

    def _content(self) -> str:
        # The id is assigned by the Wikibase instance, so two forms are considered equal when they hold the same content
        return json.dumps([self.representations.get_json(), self.grammatical_features, self.claims.get_json()], sort_keys=True)

    def __eq__(self, other):
        if not isinstance(other, Form):
            return NotImplemented

        return self._content() == other._content()

    def __hash__(self):
        # Based on the content, like __eq__: a Form modified after being added to a set or used as a dict key won't be found anymore
        return hash(self._content())
