from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType

# The field of the values holding the IRI of an entity, by value type. A bare entity ID given to a data type without
# wikibase_url (e.g. Quantity(unit='Q11573')) is kept as it is, and completed with the Wikibase URL when the value is
# serialized: the one of the WikibaseIntegrator instance of the entity serializing itself, else wbi_config's (#1193).
_ENTITY_IRI_FIELDS = {'quantity': 'unit', 'time': 'calendarmodel', 'globecoordinate': 'globe'}

# The Wikibase URL of the entity being serialized, see _serializing_for()
_serialization_wikibase_url: ContextVar[str | None] = ContextVar('wikibaseintegrator_serialization_wikibase_url', default=None)


@contextmanager
def _serializing_for(wikibase_url: str | None) -> Iterator[None]:
    """Complete the bare entity IDs of the values serialized in this block with this Wikibase URL."""
    token = _serialization_wikibase_url.set(wikibase_url)
    try:
        yield
    finally:
        _serialization_wikibase_url.reset(token)


def _is_bare_entity_id(value: object) -> bool:
    # The same test as the data types used to apply when they were built
    return isinstance(value, str) and value.startswith('Q')


def _entity_iri(value: str, wikibase_url: str | None = None) -> str:
    """The IRI of a value of an entity IRI field: a bare entity ID completed with the Wikibase URL, an IRI unchanged."""
    if not _is_bare_entity_id(value):
        return value
    return f'{wikibase_url or _serialization_wikibase_url.get() or config["WIKIBASE_URL"]}/entity/{value}'


def _resolve_datavalue(datavalue: dict, wikibase_url: str | None = None) -> dict:
    """
    The datavalue with its bare entity ID completed (see _ENTITY_IRI_FIELDS), or the datavalue itself if it has none.

    :param wikibase_url: The Wikibase URL. Default: the one of the entity being serialized, else wbi_config['WIKIBASE_URL']
    """
    field = _ENTITY_IRI_FIELDS.get(datavalue.get('type', ''))
    value = datavalue.get('value')
    if field is None or not isinstance(value, dict) or not _is_bare_entity_id(value.get(field)):
        return datavalue
    return {**datavalue, 'value': {**value, field: _entity_iri(value[field], wikibase_url)}}


def _same_entity_iri(first: object, second: object) -> bool:
    # A bare entity ID matches the IRI of this entity on any instance: the instance isn't known when the values are compared
    if first == second:
        return True
    if _is_bare_entity_id(first) and isinstance(second, str):
        return second.endswith(f'/entity/{first}')
    if _is_bare_entity_id(second) and isinstance(first, str):
        return first.endswith(f'/entity/{second}')
    return False


def _same_datavalue(first: dict, second: dict) -> bool:
    """Compare two datavalues, a bare entity ID being the same as the IRI of this entity (see _ENTITY_IRI_FIELDS)."""
    if first == second:
        return True
    field = _ENTITY_IRI_FIELDS.get(first.get('type', ''))
    first_value, second_value = first.get('value'), second.get('value')
    if field is None or first.get('type') != second.get('type') or not isinstance(first_value, dict) or not isinstance(second_value, dict):
        return False
    if {**first, 'value': None} != {**second, 'value': None}:
        return False
    return ({k: v for k, v in first_value.items() if k != field} == {k: v for k, v in second_value.items() if k != field}
            and _same_entity_iri(first_value.get(field), second_value.get(field)))


def _copy_json(snak: Snak) -> dict[str, Any]:
    """The JSON of a snak with its bare entity IDs kept as they are, to copy it, e.g. a claim added as a qualifier."""
    json_data = snak.get_json()
    if 'datavalue' in json_data:
        json_data['datavalue'] = snak.datavalue
    return json_data


def _require_property_number(snak: Snak) -> str:
    """
    The property number of a snak stored under its property, e.g. in the claims of an entity or the snaks of a reference.

    :raises ValueError: When the snak has no property number: it cannot be stored, and the Wikibase instance would reject it.
    """
    if snak.property_number is None:
        raise ValueError('The snak has no property number (prop_nr): set one to add it to claims, qualifiers or references')
    return snak.property_number


class Snak(BaseModel):
    def __init__(self, snaktype: WikibaseSnakType = WikibaseSnakType.KNOWN_VALUE, property_number: str | None = None, hash: str | None = None, datavalue: dict | None = None,
                 datatype: str | WikibaseDatatype | None = None) -> None:
        self.snaktype = snaktype
        self.property_number = property_number
        self.hash = hash
        self.datavalue = datavalue or {}
        self.datatype = datatype

    @property
    def snaktype(self) -> WikibaseSnakType:
        return self.__snaktype

    @snaktype.setter
    def snaktype(self, value: WikibaseSnakType) -> None:
        """Parse the snaktype. The enum throws an error if it is not one of the recognized values"""
        self.__snaktype = WikibaseSnakType(value)

    @property
    def property_number(self) -> str | None:
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
    def hash(self) -> str | None:
        return self.__hash

    @hash.setter
    def hash(self, value: str | None) -> None:
        self.__hash = value

    @property
    def datavalue(self) -> dict:
        return self.__datavalue

    @datavalue.setter
    def datavalue(self, value: dict | None) -> None:
        # No value is an empty dict, like in __init__: the datavalue is always a dict
        if value is not None and value != {}:
            self.snaktype = WikibaseSnakType.KNOWN_VALUE
        self.__datavalue = value if value is not None else {}

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

    def get_json(self) -> dict[str, Any]:
        """
        The JSON of the snak. A bare entity ID of its value, like the unit of a Quantity(unit='Q11573'), is completed with
        the Wikibase URL: the WIKIBASE_URL of the WikibaseIntegrator instance of the entity serializing itself, else
        wbi_config['WIKIBASE_URL'].
        """
        json_data: dict[str, Any] = {
            'snaktype': self.snaktype.value,
            'property': self.property_number,
            'datatype': self.datatype,
            'datavalue': _resolve_datavalue(self.datavalue)
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
        return self.snaktype == other.snaktype and self.property_number == other.property_number and same_datatype and _same_datavalue(self.datavalue, other.datavalue)
