from __future__ import annotations

from typing import Dict, List


class Sitelinks:
    def __init__(self):
        self.sitelinks = {}

    def get(self, site: str = None):
        if site in self.sitelinks:
            return self.sitelinks[site]

        return None

    def set(self, site: str = None, title: str = None, badges: List[str] = None) -> Sitelink:
        sitelink = Sitelink(site, title, badges)
        self.sitelinks[site] = sitelink
        return sitelink

    def from_json(self, json_data: Dict[str, Dict]) -> Sitelinks:
        for sitelink in json_data:
            self.set(site=json_data[sitelink]['site'], title=json_data[sitelink]['title'], badges=json_data[sitelink]['badges'])

        return self

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class Sitelink:
    def __init__(self, site: str = None, title: str = None, badges: List[str] = None):
        self.site = site
        self.title = title
        self.badges: List[str] = badges or []

    def __str__(self):
        return self.title

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
