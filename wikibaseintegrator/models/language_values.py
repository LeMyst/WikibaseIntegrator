class LanguageValues:
    def __init__(self):
        self.values = {}

    def get(self, language=None):
        return self.values[language]

    def set(self, language=None, value=None):
        language_value = LanguageValue(language, value)
        self.values[language] = language_value
        return language_value

    def get_json(self) -> {}:
        json_data = {}
        for value in self.values:
            json_data[value] = self.values[value].get_json()
        return json_data

    def from_json(self, json_data):
        for language_value in json_data:
            self.set(language=json_data[language_value]['language'], value=json_data[language_value]['value'])

        return self

    def __iter__(self):
        return iter(self.values.values())

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class LanguageValue:
    def __init__(self, language=None, value=None):
        self.language = language
        self.value = value
        self.removed = False

    def remove(self):
        self.removed = True
        return self

    def get_json(self) -> {}:
        json_data = {
            'language': self.language,
            'value': self.value
        }
        if self.removed:
            json_data['remove'] = ''
        return json_data

    def __str__(self):
        return self.value

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
