from __future__ import annotations

import re
from typing import Any, Dict, List

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class Snaks(BaseModel):
    def __init__(self):
        self.snaks = {}

    def get(self, property: str = None) -> Snak:
        return self.snaks[property]

    def add(self, snak: Snak) -> Snaks:
        property = snak.property_number

        if property not in self.snaks:
            self.snaks[property] = []

        self.snaks[property].append(snak)

        return self

    def from_json(self, json_data: Dict[str, List]) -> Snaks:
        for property in json_data:
            for snak in json_data[property]:
                self.add(snak=Snak().from_json(snak))

        return self

    def get_json(self) -> Dict[str, List]:
        json_data: Dict[str, List] = {}
        for property, snaks in self.snaks.items():
            if property not in json_data:
                json_data[property] = []
            for snak in snaks:
                json_data[property].append(snak.get_json())
        return json_data

    def __iter__(self):
        iterate = []
        for snak in self.snaks.values():
            iterate.extend(snak)
        return iter(iterate)

    def __len__(self):
        return len(self.snaks)


class Snak(BaseModel):
    def __init__(self, snaktype: WikibaseSnakType = WikibaseSnakType.KNOWN_VALUE, property_number: str = None, hash: str = None, datavalue: Dict = None, datatype: str = None):
        self.snaktype = snaktype
        self.property_number = property_number
        self.hash = hash
        self.datavalue = datavalue or {}
        self.datatype = datatype

    @property
    def snaktype(self):
        return self.__snaktype

    @snaktype.setter
    def snaktype(self, value: WikibaseSnakType):
        """Parse the snaktype. The enum thows an error if it is not one of the recognized values"""
        self.__snaktype = WikibaseSnakType(value)

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

            self.__property_number = 'P' + str(matches.group(1))
        else:
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
        if value is not None:
            self.snaktype = WikibaseSnakType.KNOWN_VALUE
        self.__datavalue = value

    @property
    def datatype(self):
        return self.__datatype

    @datatype.setter
    def datatype(self, value):
        self.__datatype = value

    def from_json(self, json_data: Dict[str, Any]) -> Snak:
        self.snaktype: WikibaseSnakType = WikibaseSnakType(json_data['snaktype'])
        self.property_number = json_data['property']
        if 'hash' in json_data:
            self.hash = json_data['hash']
        if 'datavalue' in json_data:
            self.datavalue = json_data['datavalue']
        if 'datatype' in json_data:  # datatype can be null with MediaInfo
            self.datatype = json_data['datatype']
        return self

    def get_json(self) -> Dict[str, str]:
        json_data = {
            'snaktype': self.snaktype.value,
            'property': self.property_number,
            'datatype': self.datatype,
            'datavalue': self.datavalue
        }

        if self.snaktype in [WikibaseSnakType.NO_VALUE, WikibaseSnakType.UNKNOWN_VALUE]:
            del json_data['datavalue']

        # datatype can be null with MediaInfo
        if not self.datatype:
            del json_data['datatype']

        return json_data

    def __eq__(self, other):
        return self.snaktype == other.snaktype and self.property_number == other.property_number and self.datatype == other.datatype and self.datavalue == other.datavalue
