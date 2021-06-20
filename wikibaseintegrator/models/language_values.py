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
        self.__language = language
        self.__value = value
        self.__removed = False

    @property
    def language(self):
        return self.__language

    @language.setter
    def language(self, value):
        self.__language = value

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = value

    @property
    def removed(self):
        return self.__removed

    @removed.setter
    def removed(self, value):
        self.__removed = value

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

    def __eq__(self, other):
        if isinstance(other, LanguageValue):
            return self.value == other.value and self.language == other.language
        else:
            return self.value == other

    def __contains__(self, item):
        return item in self.value

    def __str__(self):
        return self.value

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
