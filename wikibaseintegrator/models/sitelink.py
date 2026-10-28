from wikibaseintegrator.models.basemodel import BaseModel


class Sitelink(BaseModel):
    def __init__(self, site: str | None = None, title: str | None = None, badges: list[str] | None = None):
        self.site = site
        self.title = title
        self.badges: list[str] = badges or []

    def __str__(self):
        return self.title or ''
