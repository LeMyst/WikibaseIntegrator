from __future__ import annotations

from wikibaseintegrator.models.snaks import Snaks, Snak


class References:
    def __init__(self):
        self.references = []

    def get(self, hash=None):
        for reference in self.references:
            if reference.hash == hash:
                return reference
        return None

    # TODO: implement if_exists
    def add(self, reference=None, if_exists='REPLACE'):
        from wikibaseintegrator.models.claims import Claim
        if isinstance(reference, Claim):
            reference = Reference(snaks=Snaks().add(Snak().from_json(reference.get_json()['mainsnak'])))

        if reference is not None:
            assert isinstance(reference, Reference)

        if reference not in self.references:
            self.references.append(reference)

        return self

    def from_json(self, json_data) -> References:
        for reference in json_data:
            self.add(reference=Reference().from_json(reference))

        return self

    def get_json(self) -> []:
        json_data = []
        for reference in self.references:
            json_data.append(reference.get_json())
        return json_data

    def remove(self, reference_to_remove):
        from wikibaseintegrator.models.claims import Claim
        if isinstance(reference_to_remove, Claim):
            reference_to_remove = Reference(snaks=Snaks().add(Snak().from_json(reference_to_remove.get_json()['mainsnak'])))

        assert isinstance(reference_to_remove, Reference)

        for reference in self.references:
            if reference == reference_to_remove:
                self.references.remove(reference)
                return True

        return False

    def __iter__(self):
        return iter(self.references)

    def __len__(self):
        return len(self.references)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Reference:
    def __init__(self, snaks=None, snaks_order=None):
        self.hash = None
        self.snaks = snaks or Snaks()
        self.snaks_order = snaks_order or []

    @property
    def hash(self):
        return self.__hash

    @hash.setter
    def hash(self, value):
        self.__hash = value

    @property
    def snaks(self):
        return self.__snaks

    @snaks.setter
    def snaks(self, value):
        self.__snaks = value

    @property
    def snaks_order(self):
        return self.__snaks_order

    @snaks_order.setter
    def snaks_order(self, value):
        self.__snaks_order = value

    # TODO: implement if_exists
    def add(self, snak=None, if_exists='REPLACE'):
        from wikibaseintegrator.models.claims import Claim
        if isinstance(snak, Claim):
            snak = Snak().from_json(snak.get_json()['mainsnak'])

        if snak is not None:
            assert isinstance(snak, Snak)

        self.snaks.add(snak)

        return self

    def from_json(self, json_data) -> Reference:
        self.hash = json_data['hash']
        self.snaks = Snaks().from_json(json_data['snaks'])
        self.snaks_order = json_data['snaks-order']

        return self

    def get_json(self) -> {}:
        json_data = {
            'snaks': self.snaks.get_json(),
            'snaks-order': self.snaks_order
        }
        return json_data

    def __iter__(self):
        return iter(self.snaks)

    def __len__(self):
        return len(self.snaks)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
