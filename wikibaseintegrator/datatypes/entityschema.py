from __future__ import annotations

import re
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType


class EntitySchema(BaseDataType):
    """
    Implements the Wikibase data type 'entity-schema'
    """
    DTYPE = WikibaseDatatype.ENTITYSCHEMA
    PTYPE = 'http://wikiba.se/ontology#WikibaseEntitySchema'

    def __init__(self, value: str | int | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The EntitySchema ID to serve as the value
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str | int | None = None):
        assert isinstance(value, (str, int)) or value is None, f'Expected str or int, found {type(value)} ({value})'

        if value:
            if isinstance(value, str):
                pattern = re.compile(r'^(?:[a-zA-Z]+:)?E?([0-9]+)$')
                matches = pattern.match(value)

                if not matches:
                    raise ValueError(f"Invalid Entity Schema ID ({value}), format must be 'E[0-9]+'")

                value = int(matches.group(1))

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'entity-schema',
                    'id': f'E{value}'
                },
                'type': 'wikibase-entityid'
            }

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value, the EntitySchema being an entity URI (e.g. http://www.wikidata.org/entity/E10)
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'uri':
            raise ValueError(f"Wrong SPARQL type {type}")

        pattern = re.compile(r'^.+/(E[0-9]+)$')
        matches = pattern.match(value)
        if not matches:
            raise ValueError(f"Invalid SPARQL value {value}")

        self.set_value(value=str(matches.group(1)))

        return self

    def get_sparql_value(self, **kwargs: Any) -> str | None:
        if self.mainsnak.snaktype == WikibaseSnakType.KNOWN_VALUE:
            wikibase_url = str(kwargs['wikibase_url'] if 'wikibase_url' in kwargs else config['WIKIBASE_URL'])
            return f'<{wikibase_url}/entity/' + self.mainsnak.datavalue['value']['id'] + '>'

        return None
