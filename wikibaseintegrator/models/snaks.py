from __future__ import annotations

from typing import Optional


class Snaks:
    def __init__(self):
        self.snaks = {}

    def get(self, property=None):
        return self.snaks[property]

    def add(self, snak: Optional[Snak] = None):
        property = snak.property

        if property not in self.snaks:
            self.snaks[property] = {}

        self.snaks[property][snak.hash] = snak

        return self

    def from_json(self, json_data) -> Snaks:
        for property in json_data:
            for snak in json_data[property]:
                self.add(snak=Snak().from_json(snak))

        return self

    def get_json(self) -> {}:
        json_data = {}
        for property in self.snaks:
            if property not in json_data:
                json_data[property] = []
            for snak in self.snaks[property]:
                json_data[property].append(self.snaks[property][snak].get_json())
        return json_data

    def __iter__(self):
        iterate = []
        for snak in self.snaks.values():
            iterate.extend(snak.values())
        return iter(iterate)

    def __len__(self):
        return len(self.snaks)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Snak:
    def __init__(self):
        self.snaktype = None
        self.property = None
        self.hash = None
        self.datavalue = {}
        self.datatype = None

    def from_json(self, json_data) -> Snak:
        self.snaktype = json_data['snaktype']
        self.property = json_data['property']
        if 'hash' in json_data:
            self.hash = json_data['hash']
        if 'datavalue' in json_data:
            self.datavalue = json_data['datavalue']
        self.datatype = json_data['datatype']
        return self

    def get_json(self) -> {}:
        json_data = {
            'snaktype': self.snaktype,
            'property': self.property,
            'datatype': self.datatype
        }
        if self.snaktype not in {'novalue', 'somevalue'}:
            json_data['datavalue'] = self.datavalue

        return json_data

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
