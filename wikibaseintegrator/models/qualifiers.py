from __future__ import annotations

from wikibaseintegrator.models.snaks import Snak


class Qualifiers:
    def __init__(self):
        self.qualifiers = {}

    def get(self, property=None):
        return self.qualifiers[property]

    # TODO: implement if_exists
    def add(self, qualifier=None, if_exists='REPLACE'):
        from wikibaseintegrator.models.claims import Claim
        if isinstance(qualifier, Claim):
            qualifier = Snak().from_json(qualifier.get_json()['mainsnak'])

        if qualifier is not None:
            assert isinstance(qualifier, Snak)

        property = qualifier.property_number

        if property not in self.qualifiers:
            self.qualifiers[property] = []

        self.qualifiers[property].append(qualifier)

        return self

    def from_json(self, json_data) -> Qualifiers:
        for property in json_data:
            for snak in json_data[property]:
                self.add(qualifier=Snak().from_json(snak))
        return self

    def get_json(self) -> {}:
        json_data = {}
        for property in self.qualifiers:
            if property not in json_data:
                json_data[property] = []

            for qualifier in self.qualifiers[property]:
                json_data[property].append(qualifier.get_json())
        return json_data

    def __len__(self):
        return len(self.qualifiers)
