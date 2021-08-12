from __future__ import annotations

from wikibaseintegrator.entities.baseentity import BaseEntity
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels


class MediaInfo(BaseEntity):
    ETYPE = 'mediainfo'

    def __init__(self, api, labels=None, descriptions=None, aliases=None, sitelinks=None, **kwargs) -> None:
        """

        :param api:
        :param labels:
        :param descriptions:
        :param aliases:
        :param sitelinks:
        :param kwargs:
        """
        self.api = api

        super(MediaInfo, self).__init__(api=self.api, **kwargs)

        # Item and property specific
        self.labels = labels or Labels()
        self.descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    def new(self, **kwargs) -> MediaInfo:
        return MediaInfo(self.api, **kwargs)

    def get(self, entity_id, **kwargs) -> MediaInfo:
        json_data = super(MediaInfo, self).get(entity_id=entity_id, **kwargs)
        return MediaInfo(self.api).from_json(json_data=json_data['entities'][entity_id])

    def get_by_title(self, title, sites='commonswiki', **kwargs) -> MediaInfo:
        params = {
            'action': 'wbgetentities',
            'sites': sites,
            'titles': title,
            'format': 'json'
        }

        json_data = self.api.helpers.mediawiki_api_call_helper(data=params, allow_anonymous=True, **kwargs)

        if len(json_data['entities'].keys()) == 0:
            raise Exception('Title not found')
        if len(json_data['entities'].keys()) > 1:
            raise Exception('More than one element for this title')

        return MediaInfo(self.api).from_json(json_data=json_data['entities'][list(json_data['entities'].keys())[0]])

    def get_json(self) -> {}:
        return {
            'labels': self.labels.get_json(),
            'descriptions': self.descriptions.get_json(),
            'aliases': self.aliases.get_json(),
            **super(MediaInfo, self).get_json()
        }

    def from_json(self, json_data) -> MediaInfo:
        super(MediaInfo, self).from_json(json_data=json_data)

        self.labels = Labels().from_json(json_data['labels'])
        self.descriptions = Descriptions().from_json(json_data['descriptions'])

        return self

    def write(self, allow_anonymous=False):
        json_data = super(MediaInfo, self)._write(data=self.get_json(), allow_anonymous=allow_anonymous)
        return self.from_json(json_data=json_data)
