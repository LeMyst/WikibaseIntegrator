from __future__ import annotations

from typing import Dict

from wikibaseintegrator.models.language_values import LanguageValue, LanguageValues


class Labels(LanguageValues):
    def from_json(self, json_data: Dict[str, Dict]) -> Labels:
        """
        Create a new Labels object from a JSON/dict object.

        :param json_data: A dict object who use the same format as Wikibase.
        :return: The newly created or updated object.
        """
        for language_value in json_data:
            self.add(language_value=LanguageValue(language=json_data[language_value]['language']).from_json(json_data=json_data[language_value]))

        return self
