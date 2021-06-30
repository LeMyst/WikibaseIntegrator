from __future__ import annotations

import re
from typing import Optional


class Snaks:
    def __init__(self):
        self.snaks = {}

    def get(self, property=None):
        return self.snaks[property]

    def add(self, snak: Optional[Snak] = None):
        property = snak.property_number

        if property not in self.snaks:
            self.snaks[property] = []

        self.snaks[property].append(snak)

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
                json_data[property].append(snak.get_json())
        return json_data

    def __iter__(self):
        iterate = []
        for snak in self.snaks.values():
            iterate.extend(snak)
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
    def __init__(self, snaktype=None, property_number=None, hash=None, datavalue=None, datatype=None):
        self.snaktype = snaktype or 'value'
        self.property_number = property_number
        self.hash = hash
        self.datavalue = datavalue or {}
        self.datatype = datatype

    @property
    def snaktype(self):
        return self.__snaktype

    @snaktype.setter
    def snaktype(self, value):
        if value not in ['value', 'novalue', 'somevalue']:
            raise ValueError('{} is not a valid snak type'.format(value))

        self.__snaktype = value

    @property
    def property_number(self):
        return self.__property_number

    @property_number.setter
    def property_number(self, value):
        if isinstance(value, int):
            self.__property_number = 'P' + str(value)
        elif value is not None:
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError('Invalid property_number, format must be "P[0-9]+"')
            else:
                self.__property_number = 'P' + str(matches.group(1))

        self.__property_number = value

    @property
    def hash(self):
        return self.__hash

    @hash.setter
    def hash(self, value):
        self.__hash = value

    @property
    def datavalue(self):
        return self.__datavalue

    @datavalue.setter
    def datavalue(self, value):
        self.__datavalue = value

    @property
    def datatype(self):
        return self.__datatype

    @datatype.setter
    def datatype(self, value):
        self.__datatype = value

    def from_json(self, json_data) -> Snak:
        self.snaktype = json_data['snaktype']
        self.property_number = json_data['property']
        if 'hash' in json_data:
            self.hash = json_data['hash']
        if 'datavalue' in json_data:
            self.datavalue = json_data['datavalue']
        self.datatype = json_data['datatype']
        return self

    def get_json(self) -> {}:
        json_data = {
            'snaktype': self.snaktype,
            'property': self.property_number,
            'datatype': self.datatype,
            'datavalue': self.datavalue
        }

        if self.snaktype in {'novalue', 'somevalue'}:
            del json_data['datavalue']

        return json_data

    def __eq__(self, other):
        return self.snaktype == other.snaktype and self.property_number == other.property_number and self.datatype == other.datatype and self.datavalue == other.datavalue

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
