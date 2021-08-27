from __future__ import annotations

import copy
from typing import Union

from wikibaseintegrator.models.qualifiers import Qualifiers
from wikibaseintegrator.models.references import References
from wikibaseintegrator.models.snaks import Snak


class Claims:
    def __init__(self):
        self.claims = {}

    @property
    def claims(self):
        return self.__claims

    @claims.setter
    def claims(self, claims):
        self.__claims = claims

    def get(self, property=None) -> list:
        return self.claims[property]

    def add(self, claims: Union[list, Claim, None] = None, if_exists='REPLACE') -> Claims:
        """

        :param claims:
        :param if_exists: Replace or append the statement. You can force an append if the statement already exists.
        :type if_exists: A string of one of three allowed values: 'REPLACE', 'APPEND', 'FORCE_APPEND', 'KEEP'
        :return: Claims
        """

        if if_exists not in ['REPLACE', 'APPEND', 'FORCE_APPEND', 'KEEP']:
            raise ValueError('{} is not a valid if_exists value'.format(if_exists))

        if isinstance(claims, Claim):
            claims = [claims]
        elif not isinstance(claims, list):
            raise ValueError

        # TODO: Don't replace if claim is the same
        if if_exists == 'REPLACE':
            for claim in claims:
                if claim is not None:
                    assert isinstance(claim, Claim)
                property = claim.mainsnak.property_number
                if property in self.claims:
                    for claim_to_remove in self.claims[property]:
                        if claim_to_remove not in claims:
                            claim_to_remove.remove()

        for claim in claims:
            if claim is not None:
                assert isinstance(claim, Claim)
            property = claim.mainsnak.property_number

            if property not in self.claims:
                self.claims[property] = []

            if if_exists == 'KEEP':
                if len(self.claims[property]) == 0:
                    self.claims[property].append(claim)
            elif if_exists == 'FORCE_APPEND':
                self.claims[property].append(claim)
            elif if_exists == 'APPEND':
                if claim not in self.claims[property]:
                    self.claims[property].append(claim)
            elif if_exists == 'REPLACE':
                if claim not in self.claims[property]:
                    self.claims[property].append(claim)

        return self

    def from_json(self, json_data) -> Claims:
        for property in json_data:
            for claim in json_data[property]:
                from wikibaseintegrator.datatypes import BaseDataType
                if 'datatype' in 'mainsnak':
                    data_type = [x for x in BaseDataType.subclasses if x.DTYPE == claim['mainsnak']['datatype']][0]
                else:
                    data_type = Claim
                self.add(claims=data_type().from_json(claim), if_exists='FORCE_APPEND')

        return self

    def get_json(self) -> {}:
        json_data = {}
        for property in self.claims:
            if property not in json_data:
                json_data[property] = []
            for claim in self.claims[property]:
                json_data[property].append(claim.get_json())
        return json_data

    def clear(self):
        self.claims = {}

    def __len__(self):
        return len(self.claims)

    def __iter__(self):
        iterate = []
        for claim in self.claims.values():
            iterate.extend(claim)
        return iter(iterate)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )


class Claim:
    DTYPE = 'claim'
    subclasses = []

    def __init__(self, **kwargs):
        self.mainsnak = Snak(datatype=self.DTYPE)
        self.type = 'statement'
        self.qualifiers = kwargs.pop('qualifiers', Qualifiers())
        self.qualifiers_order = []
        self.id = None
        self.rank = kwargs.pop('rank', 'normal')
        self.references = kwargs.pop('references', References())
        self.removed = False

    # Allow registration of subclasses of Claim into Claim.subclasses
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

    @property
    def mainsnak(self):
        return self.__mainsnak

    @mainsnak.setter
    def mainsnak(self, value):
        self.__mainsnak = value

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, value):
        self.__type = value

    @property
    def qualifiers(self):
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value):
        assert isinstance(value, (Qualifiers, list))
        if isinstance(value, list):
            self.__qualifiers = Qualifiers().set(value)
        else:
            self.__qualifiers = value

    @property
    def qualifiers_order(self):
        return self.__qualifiers_order

    @qualifiers_order.setter
    def qualifiers_order(self, value):
        self.__qualifiers_order = value

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, value):
        self.__id = value

    @property
    def rank(self):
        return self.__rank

    @rank.setter
    def rank(self, value):
        if value not in ['normal', 'deprecated', 'preferred']:
            raise ValueError("{} not a valid rank".format(value))

        self.__rank = value

    @property
    def references(self):
        return self.__references

    @references.setter
    def references(self, value):
        self.__references = value

    @property
    def removed(self):
        return self.__removed

    @removed.setter
    def removed(self, value):
        self.__removed = value

    def remove(self, remove=True):
        self.removed = remove

    def from_json(self, json_data) -> Claim:
        self.mainsnak = Snak().from_json(json_data['mainsnak'])
        self.type = json_data['type']
        if 'qualifiers' in json_data:
            self.qualifiers = Qualifiers().from_json(json_data['qualifiers'])
        if 'qualifiers-order' in json_data:
            self.qualifiers_order = json_data['qualifiers-order']
        self.id = json_data['id']
        self.rank = json_data['rank']
        if 'references' in json_data:
            self.references = References().from_json(json_data['references'])

        return self

    def get_json(self) -> {}:
        json_data = {
            'mainsnak': self.mainsnak.get_json(),
            'type': self.type,
            'id': self.id,
            'rank': self.rank
        }
        # Remove id if it's a temporary one
        if not self.id:
            del json_data['id']
        if len(self.qualifiers) > 0:
            json_data['qualifiers'] = self.qualifiers.get_json()
            json_data['qualifiers-order'] = self.qualifiers_order
        if len(self.references) > 0:
            json_data['references'] = self.references.get_json()
        if self.removed:
            json_data['remove'] = ''
        return json_data

    def has_equal_qualifiers(self, other):
        # check if the qualifiers are equal with the 'other' object
        equal_qualifiers = True
        self_qualifiers = copy.deepcopy(self.qualifiers)
        other_qualifiers = copy.deepcopy(other.qualifiers)

        if len(self_qualifiers) != len(other_qualifiers):
            equal_qualifiers = False
        else:
            flg = [False for _ in range(len(self_qualifiers))]
            for count, i in enumerate(self_qualifiers):
                for q in other_qualifiers:
                    if i == q:
                        flg[count] = True
            if not all(flg):
                equal_qualifiers = False

        return equal_qualifiers

    def __contains__(self, item):
        if isinstance(item, Claim):
            return self == item
        elif isinstance(item, str):
            return self.mainsnak.datavalue == item
        raise TypeError

    def __eq__(self, other):
        if isinstance(other, Claim):
            return self.mainsnak.datavalue == other.mainsnak.datavalue and self.mainsnak.property_number == other.mainsnak.property_number and self.has_equal_qualifiers(other)
        raise TypeError

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
