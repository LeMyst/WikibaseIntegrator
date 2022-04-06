from __future__ import annotations

import re
from typing import Any, Dict, List, Union

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models import Claims, LanguageValues
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper


class MediaInfoEntity(BaseEntity):
    ETYPE = 'mediainfo'

    def __init__(self, labels: Labels = None, descriptions: Descriptions = None, aliases: Aliases = None, **kwargs: Any) -> None:
        """

        :param api:
        :param labels:
        :param descriptions:
        :param aliases:
        :param sitelinks:
        :param kwargs:
        """
        super().__init__(**kwargs)

        # Item, Property and MediaInfo specific
        self.labels: LanguageValues = labels or Labels()
        self.descriptions: LanguageValues = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    def new(self, **kwargs: Any) -> MediaInfoEntity:
        return MediaInfoEntity(api=self.api, **kwargs)

    def get(self, entity_id: Union[str, int], **kwargs: Any) -> MediaInfoEntity:
        if isinstance(entity_id, str):
            pattern = re.compile(r'^M?([0-9]+)$')
            matches = pattern.match(entity_id)

            if not matches:
                raise ValueError(f"Invalid MediaInfo ID ({entity_id}), format must be 'M[0-9]+'")

            entity_id = int(matches.group(1))

        if entity_id < 1:
            raise ValueError("MediaInfo ID must be greater than 0")

        entity_id = f'M{entity_id}'
        json_data = super()._get(entity_id=entity_id, **kwargs)
        return MediaInfoEntity(api=self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_by_title(self, titles: Union[List[str], str], sites: str = 'commonswiki', **kwargs: Any) -> MediaInfoEntity:
        if isinstance(titles, list):
            titles = '|'.join(titles)

        params = {
            'action': 'wbgetentities',
            'sites': sites,
            'titles': titles,
            'format': 'json'
        }

        json_data = mediawiki_api_call_helper(data=params, allow_anonymous=True, **kwargs)

        if len(json_data['entities'].keys()) == 0:
            raise Exception('Title not found')
        if len(json_data['entities'].keys()) > 1:
            raise Exception('More than one element for this title')

        return MediaInfoEntity(api=self.api).from_json(json_data=json_data['entities'][list(json_data['entities'].keys())[0]])

    def get_json(self) -> Dict[str, Union[str, Dict]]:
        return {
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            **super().get_json()
        }

        # if 'claims' in json_data:  # MediaInfo change name of 'claims' to 'statements'
        #     json_data['statements'] = json_data.pop('claims')

        # if 'statements' in json_data:
        #     for prop_nr in json_data['statements']:
        #         for statement in json_data['statements'][prop_nr]:
        #             if 'mainsnak' in statement and 'datatype' in statement['mainsnak']:
        #                 del statement['mainsnak']['datatype']

    def from_json(self, json_data: Dict[str, Any]) -> MediaInfoEntity:
        super().from_json(json_data=json_data)

        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])
        self.claims = Claims().from_json(json_data['statements'])

        return self

    def write(self, **kwargs: Any) -> MediaInfoEntity:
        """
        Write the MediaInfoEntity data to the Wikibase instance and return the MediaInfoEntity object returned by the instance.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: Clear the existing entity before updating
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: an MediaInfoEntity of the response from the instance
        """
        json_data = super()._write(data=self.get_json(), **kwargs)
        return self.from_json(json_data=json_data)
