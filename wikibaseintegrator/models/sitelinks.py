class Sitelinks:
    def __init__(self):
        self.sitelinks = {}

    def get(self, site=None):
        if site in self.sitelinks:
            return self.sitelinks[site]

        return None

    def set(self, site=None, title=None, badges=None):
        sitelink = Sitelink(site, title, badges)
        self.sitelinks[site] = sitelink
        return sitelink

    def from_json(self, json_data):
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
    def __init__(self, site=None, title=None, badges=None):
        self.site = site
        self.title = title
        self.badges = badges

    def __str__(self):
        return self.title

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
