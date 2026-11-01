from __future__ import annotations

import re
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class Snak(BaseModel):
    def __init__(self, snaktype: WikibaseSnakType = WikibaseSnakType.KNOWN_VALUE, property_number: str | None = None, hash: str | None = None, datavalue: dict | None = None,
                 datatype: str | WikibaseDatatype | None = None) -> None:
        self.snaktype = snaktype
        self.property_number = property_number
        self.hash = hash
        self.datavalue = datavalue or {}
        self.datatype = datatype

    @property
    def snaktype(self):
        return self.__snaktype

    @snaktype.setter
    def snaktype(self, value: WikibaseSnakType) -> None:
        """Parse the snaktype. The enum throws an error if it is not one of the recognized values"""
        self.__snaktype = WikibaseSnakType(value)

    @property
    def property_number(self):
        return self.__property_number

    @property_number.setter
    def property_number(self, value: str | int | None) -> None:
        if isinstance(value, int):
            self.__property_number: str | None = 'P' + str(value)
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
    def hash(self, value: str | None) -> None:
        self.__hash = value

    @property
    def datavalue(self):
        return self.__datavalue

    @datavalue.setter
    def datavalue(self, value: dict | None) -> None:
        if value is not None and value != {}:
            self.snaktype = WikibaseSnakType.KNOWN_VALUE
        self.__datavalue = value

    @property
    def datatype(self) -> WikibaseDatatype | str | None:
        return self.__datatype

    @datatype.setter
    def datatype(self, value: str | WikibaseDatatype | None) -> None:
        # A known datatype is stored as a WikibaseDatatype member, which is also equal to its string value
        self.__datatype = WikibaseDatatype.from_value(value)

    def from_json(self, json_data: dict[str, Any]) -> Self:
        self.snaktype: WikibaseSnakType = WikibaseSnakType(json_data['snaktype'])
        self.property_number = json_data['property']
        if 'hash' in json_data:
            self.hash = json_data['hash']
        if 'datavalue' in json_data:
            self.datavalue = json_data['datavalue']
        if 'datatype' in json_data:  # datatype can be null with MediaInfo
            self.datatype = json_data['datatype']
        return self

    def get_json(self) -> dict[str, str]:
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
        else:
            # A plain string in the JSON representation, not a WikibaseDatatype member
            json_data['datatype'] = str(self.datatype)

        return json_data

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Snak):
            return NotImplemented

        # The datatype is only compared when both snaks have one: the property determines it, and Commons serves the snaks of the
        # MediaInfo statements without a datatype, while the snaks built with WikibaseIntegrator carry one
        same_datatype = not self.datatype or not other.datatype or self.datatype == other.datatype
        return self.snaktype == other.snaktype and self.property_number == other.property_number and same_datatype and self.datavalue == other.datavalue
