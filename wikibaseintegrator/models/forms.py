from wikibaseintegrator.models.claims import Claims


class Forms:
    def __init__(self):
        self.forms = {}

    def get(self, id):
        return self.forms[id]

    def add(self, form):
        self.forms[form.id] = form

    def get_json(self) -> []:
        json_data = []
        for form in self.forms:
            json_data.append(self.forms[form].get_json())
        return json_data

    def from_json(self, json_data):
        for form in json_data:
            self.add(Form(form_id=form['id'], representations=form['representations'], grammatical_features=form['grammaticalFeatures'],
                          claims=Claims().from_json(form['claims'])))

        return self

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Form:
    def __init__(self, form_id=None, representations=None, grammatical_features=None, claims=None):
        self.id = form_id
        self.representations = representations
        self.grammatical_features = grammatical_features
        self.claims = claims

    def get_json(self) -> {}:
        return {
            'id': self.id,
            'representations': self.representations.get_json(),
            'grammaticalFeatures': self.grammatical_features.get_json(),
            'claims': self.claims.get_json()
        }

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
