from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues


class Senses:
    def __init__(self):
        self.senses = []

    def get(self, id):
        for sense in self.senses:
            if sense.id == id:
                return sense
        return None

    # TODO: implement if_exists
    def add(self, sense, if_exists='REPLACE'):
        self.senses.append(sense)

    def get_json(self) -> []:
        json_data = []
        for sense in self.senses:
            json_data.append(sense.get_json())
        return json_data

    def from_json(self, json_data):
        for sense in json_data:
            self.add(Sense(sense_id=sense['id'], glosses=Glosses().from_json(sense['glosses']), claims=Claims().from_json(sense['claims'])))

        return self

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Sense:
    def __init__(self, sense_id=None, glosses=None, claims=None):
        self.id = sense_id
        self.glosses = glosses or Glosses()
        self.claims = claims or Claims()
        self.removed = False

    def get_json(self) -> {}:
        json_data = {
            'id': self.id,
            'glosses': self.glosses.get_json(),
            'claims': self.claims.get_json()
        }

        if self.id is None:
            json_data['add'] = ''
            del json_data['id']

        if self.removed:
            json_data['remove'] = ''

        return json_data

    def remove(self):
        self.removed = True
        return self

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Glosses(LanguageValues):
    pass
