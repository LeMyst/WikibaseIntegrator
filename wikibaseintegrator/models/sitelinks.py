from __future__ import annotations

from typing import Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.sitelink import Sitelink


class Sitelinks(BaseModel):
    def __init__(self) -> None:
        self.sitelinks: dict[str, Sitelink] = {}

    def get(self, site: str | None = None) -> Sitelink | None:
        if site in self.sitelinks:
            return self.sitelinks[site]

        return None

    def set(self, site: str, title: str | None = None, badges: list[str] | None = None) -> Sitelink:
        sitelink = Sitelink(site, title, badges)
        self.sitelinks[site] = sitelink
        return sitelink

    def get_json(self) -> dict[str, dict]:
        return {
            sitelink:
                {
                    'site': self.sitelinks[sitelink].site,
                    'title': self.sitelinks[sitelink].title,
                    'badges': self.sitelinks[sitelink].badges
                } for sitelink in self.sitelinks
        }

    def from_json(self, json_data: dict[str, dict]) -> Self:
        for sitelink in json_data:
            self.set(site=json_data[sitelink]['site'], title=json_data[sitelink]['title'], badges=json_data[sitelink]['badges'])

        return self

    def __len__(self):
        return len(self.sitelinks)
