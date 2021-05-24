from __future__ import annotations

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class Claims:
    def __init__(self, api=None):
        self.claims = {}
        self.api = api

    def get(self, property=None) -> dict:
        return self.claims[property]

    def add(self, claims=None) -> Claims:
        if isinstance(claims, BaseDataType):
            claims = [claims]
        elif not isinstance(claims, list):
            raise ValueError

        for claim in claims:
            property = claim.prop_nr
            if claim is not None:
                assert isinstance(claim, BaseDataType)

            if property is None:
                property = claim.prop_nr

            if property not in self.claims:
                self.claims[property] = {}

            self.claims[property][claim.id] = claim

        return self

    def get_json(self) -> {}:
        json_data = {}
        for property in self.claims:
            if property not in json_data:
                json_data[property] = []
            for claim in self.claims[property]:
                json_data[property].append(self.claims[property][claim].get_json_representation())
        return json_data

    def from_json(self, json_data) -> Claims:
        for property in json_data:
            for alias in json_data[property]:
                data_type = [x for x in BaseDataType.__subclasses__() if x.DTYPE == alias['mainsnak']['datatype']][0]
                self.add(data_type.from_json(alias))

        return self

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )

    def __iter__(self):
        return iter(self.claims.values())
