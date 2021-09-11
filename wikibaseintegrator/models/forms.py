from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.language_values import LanguageValues


class Forms:
    def __init__(self):
        self.forms = {}

    @property
    def forms(self):
        return self.__forms

    @forms.setter
    def forms(self, value):
        self.__forms = value

    def get(self, id):
        return self.forms[id]

    def add(self, form):
        self.forms[form.id] = form

        return self

    def get_json(self) -> []:
        json_data = []
        for form in self.forms:
            json_data.append(self.forms[form].get_json())
        return json_data

    def from_json(self, json_data):
        for form in json_data:
            self.add(Form(form_id=form['id'], representations=LanguageValues().from_json(form['representations']), grammatical_features=form['grammaticalFeatures'],
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
        self.representations = representations or LanguageValues()
        self.grammatical_features = grammatical_features or []
        self.claims = claims or Claims()

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, value):
        self.__id = value

    @property
    def representations(self):
        return self.__representations

    @representations.setter
    def representations(self, value):
        self.__representations = value

    @property
    def grammatical_features(self):
        return self.__grammatical_features

    @grammatical_features.setter
    def grammatical_features(self, value):
        # TODO: Access to member before its definition
        if isinstance(value, int):
            self.__grammatical_features.append('Q' + str(value))
        elif isinstance(value, str):
            self.__grammatical_features.append(value)
        else:
            self.__grammatical_features = value

    @property
    def claims(self):
        return self.__claims

    @claims.setter
    def claims(self, value):
        self.__claims = value

    def get_json(self) -> {}:
        json_data = {
            'id': self.id,
            'representations': self.representations.get_json(),
            'grammaticalFeatures': self.grammatical_features,
            'claims': self.claims.get_json()
        }

        if self.id is None:
            json_data['add'] = ''
            del json_data['id']

        return json_data

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
