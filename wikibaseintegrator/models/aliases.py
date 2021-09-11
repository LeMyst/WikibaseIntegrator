from wikibaseintegrator.models.language_values import LanguageValue
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists


class Aliases:
    def __init__(self, language=None, value=None):
        self.__aliases = {}

        if language is not None:
            self.set(language=language, values=value)

    @property
    def aliases(self):
        return self.__aliases

    @aliases.setter
    def aliases(self, value):
        self.__aliases = value

    def get(self, language=None):
        if language is None:
            # TODO: Don't return a list of list, just a list
            return [item for sublist in self.aliases.values() for item in sublist]

        if language in self.aliases:
            return self.aliases[language]

        return None

    def set(self, language=None, values=None, action_if_exists=ActionIfExists.APPEND):
        language = language or config['DEFAULT_LANGUAGE']
        assert action_if_exists in ActionIfExists

        assert language is not None

        if language not in self.aliases:
            self.aliases[language] = []

        if values is None or values == '':
            if action_if_exists != ActionIfExists.KEEP:
                for alias in self.aliases[language]:
                    alias.remove()
            return self.aliases[language]

        if isinstance(values, str):
            values = [values]
        elif not isinstance(values, list) and values is not None:
            raise TypeError("value must be a str or list")

        if action_if_exists == ActionIfExists.REPLACE:
            aliases = []
            for value in values:
                alias = Alias(language, value)
                aliases.append(alias)
            self.aliases[language] = aliases
        else:
            for value in values:
                alias = Alias(language, value)

                if action_if_exists == ActionIfExists.APPEND:
                    if alias not in self.aliases[language]:
                        self.aliases[language].append(alias)
                elif action_if_exists == ActionIfExists.KEEP:
                    if not self.aliases[language]:
                        self.aliases[language].append(alias)

        return self

    def get_json(self) -> {}:
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

    # def __contains__(self, item):
    #     all_aliases = [item for sublist in list(self.aliases.values()) for item in sublist]
    #     return item in list(map(lambda x: x.value, all_aliases))

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Alias(LanguageValue):
    pass
