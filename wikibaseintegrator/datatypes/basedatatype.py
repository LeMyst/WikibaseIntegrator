from __future__ import annotations

import re
from typing import Any, Self

from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.wbi_enums import WikibaseSnakType
from wikibaseintegrator.wbi_exceptions import UnknownDatatypeError


class BaseDataType(Claim):
    """
    The base class for all Wikibase data types, they inherit from it
    """
    DTYPE = 'base-data-type'
    PTYPE = 'property-data-type'
    subclasses: list[type[BaseDataType]] = []
    sparql_query: str = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}' .
        }}
    '''

    def __init__(self, prop_nr: int | str | None = None, **kwargs: Any):
        """
        Constructor, will be called by all data types.

        :param prop_nr: The property number a Wikibase snak belongs to
        """

        super().__init__(**kwargs)

        if isinstance(prop_nr, str):
            pattern = re.compile(r'^([a-z][a-z\d+.-]*):([^][<>\"\x00-\x20\x7F])+$')
            matches = pattern.match(str(prop_nr))

            if matches:
                prop_nr = prop_nr.rsplit('/', 1)[-1]

        self.mainsnak.property_number = prop_nr
        # self.subclasses.append(self)

    # Allow registration of subclasses of BaseDataType into BaseDataType.subclasses
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

    @classmethod
    def get_datatype_class(cls, datatype: str) -> type[BaseDataType]:
        """
        Find the data type class handling a datatype, as named by the Wikibase API.

        :param datatype: The datatype, e.g. 'wikibase-item' or WikibaseDatatype.ITEM
        :return: The data type class, e.g. Item
        :raises UnknownDatatypeError: If no data type class handles this datatype
        """
        for subclass in cls.subclasses:
            if subclass.DTYPE == datatype:
                return subclass

        raise UnknownDatatypeError(datatype=str(datatype), supported=sorted(str(subclass.DTYPE) for subclass in cls.subclasses))

    @staticmethod
    def _is_unknown_value(sparql_value: dict) -> bool:
        """
        Whether a value returned by a SPARQL endpoint is an unknown value ("some value" snak), whatever the data type. The
        RDF export represents it as a skolem IRI under the concept URI of the instance, e.g.
        http://www.wikidata.org/.well-known/genid/<hash> on Wikidata or https://example.wikibase.cloud/.well-known/genid/<hash>,
        or as a blank node on older query services.

        :param sparql_value: A SPARQL value composed of type and value
        """
        if sparql_value.get('type') == 'bnode':
            return True
        return sparql_value.get('type') == 'uri' and '/.well-known/genid/' in sparql_value.get('value', '')

    def set_value(self, value: Any | None = None):
        pass

    def get_sparql_value(self, **kwargs: Any) -> str | None:
        return '"' + self.mainsnak.datavalue['value'] + '"'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        if type == 'uri':
            pattern = re.compile(r'^<?(.*?)>?$')
            matches = pattern.match(value)
            if not matches:
                return False

            self.set_value(value=matches.group(1))
        elif type == 'literal':
            pattern = re.compile(r'^"?(.*?)"?$')
            matches = pattern.match(value)
            if not matches:
                return False

            self.set_value(value=matches.group(1))
        else:
            raise ValueError

        return True

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        This generic implementation covers the data types whose RDF representation is the literal value itself
        (external identifiers, musical notation...). The data types backed by a URI (entities, media files) override
        it to extract the value from that URI, since storing the raw URI would silently never match a local claim.

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'literal':
            raise ValueError(f"Wrong SPARQL type {type}")

        self.set_value(value=value)

        return self
