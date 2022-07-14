from __future__ import annotations

from typing import Dict, List, Optional

from wikibaseintegrator.models.basemodel import BaseModel


class Sitelinks(BaseModel):
    def __init__(self):
        self.sitelinks: Dict[str, Sitelink] = {}

    def get(self, site: str = None) -> Optional[Sitelink]:
        if site in self.sitelinks:
            return self.sitelinks[site]

        return None

    def set(self, site: str, title: str = None, badges: List[str] = None) -> Sitelink:
        sitelink = Sitelink(site, title, badges)
        self.sitelinks[site] = sitelink
        return sitelink

    def from_json(self, json_data: Dict[str, Dict]) -> Sitelinks:
        for sitelink in json_data:
            self.set(site=json_data[sitelink]['site'], title=json_data[sitelink]['title'], badges=json_data[sitelink]['badges'])

        return self


class Sitelink(BaseModel):
    def __init__(self, site: str = None, title: str = None, badges: List[str] = None):
        self.site = site
        self.title = title
        self.badges: List[str] = badges or []

    def __str__(self):
        return self.title
