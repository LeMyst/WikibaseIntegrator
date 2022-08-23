from __future__ import annotations

from typing import List

from wikibaseintegrator.models.basemodel import BaseModel


class Sitelink(BaseModel):
    def __init__(self, site: str = None, title: str = None, badges: List[str] = None):
        self.site = site
        self.title = title
        self.badges: List[str] = badges or []

    def __str__(self):
        return self.title
