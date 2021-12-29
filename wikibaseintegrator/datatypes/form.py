import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class Form(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-form'
    """
    DTYPE = 'wikibase-form'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value: str = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param value: The form number to serve as a value using the format "L<Lexeme ID>-F<Form ID>" (example: L252248-F2)
        :type value: str with the format "L<Lexeme ID>-F<Form>"
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super().__init__(**kwargs)
        self.set_value(value=value)

    def set_value(self, value: str = None):
        assert isinstance(value, str) or value is None, f"Expected str, found {type(value)} ({value})"

        if value:
            pattern = re.compile(r'^L[0-9]+-F[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError(f"Invalid form ID ({value}), format must be 'L[0-9]+-F[0-9]+'")

            self.mainsnak.datavalue = {
                'value': {
                    'entity-type': 'form',
                    'id': value
                },
                'type': 'wikibase-entityid'
            }

    def get_sparql_value(self) -> str:
        return self.mainsnak.datavalue['value']['id']
