from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class Qualifiers:
    def __init__(self):
        self.qualifiers = {}

    def get(self, property=None):
        return self.qualifiers[property]

    def add(self, property=None, qualifier=None):
        if qualifier is not None:
            assert isinstance(qualifier, BaseDataType)

        if property is None:
            property = qualifier.prop_nr

        if property not in self.qualifiers:
            self.qualifiers[property] = {}

        self.qualifiers[property] = qualifier

        return self
