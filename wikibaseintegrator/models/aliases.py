from wikibaseintegrator.models.language_values import LanguageValue


class Aliases:
    def __init__(self, language=None, value=None):
        self.aliases = {}

        if language is not None:
            self.set(language=language, value=value)

    def get(self, language=None):
        return self.aliases[language]

    def set(self, language=None, value=None):
        if language not in self.aliases:
            self.aliases[language] = []
        alias = Alias(language, value)
        self.aliases[language].append(alias)
        return alias

    def get_json(self) -> []:
        json_data = {}
        for language in self.aliases:
            if language not in json_data:
                json_data[language] = []
            for alias in self.aliases[language]:
                json_data[language].append(alias.get_json())
        return json_data

    def from_json(self, json_data):
        for language in json_data:
            for alias in json_data[language]:
                self.set(alias['language'], alias['value'])

        return self

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Alias(LanguageValue):
    pass
