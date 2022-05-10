from __future__ import annotations

from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType
from wikibaseintegrator.wbi_helpers import format_amount


class Quantity(BaseDataType):
    """
    Implements the Wikibase data type for quantities
    """
    DTYPE = 'quantity'
    PTYPE = 'http://wikiba.se/ontology#Quantity'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:decimal .
        }}
    '''

    def __init__(self, amount: str | int | float | None = None, upper_bound: str | int | float | None = None, lower_bound: str | int | float | None = None, unit: str | int = '1',
                 wikibase_url: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param amount: The amount value
        :param upper_bound: Upper bound of the value if it exists, e.g. for standard deviations
        :param lower_bound: Lower bound of the value if it exists, e.g. for standard deviations
        :param unit: The unit item URL or the QID a certain amount has been measured in (https://www.wikidata.org/wiki/Wikidata:Units).
            The default is dimensionless, represented by a '1'
        :param wikibase_url: The default wikibase URL, used when the unit is only an ID like 'Q2'. Use wbi_config['WIKIBASE_URL'] by default.
        """

        super().__init__(**kwargs)
        self.set_value(amount=amount, upper_bound=upper_bound, lower_bound=lower_bound, unit=unit, wikibase_url=wikibase_url)

    def set_value(self, amount: str | int | float | None = None, upper_bound: str | int | float | None = None, lower_bound: str | int | float | None = None, unit: str | int = '1',
                  wikibase_url: str | None = None):
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        unit = str(unit or '1')

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        if amount is not None:
            amount = format_amount(amount)
            unit = str(unit)
            if upper_bound:
                upper_bound = format_amount(upper_bound)
            if lower_bound:
                lower_bound = format_amount(lower_bound)

            # Integrity checks for value and bounds
            try:
                for i in [amount, upper_bound, lower_bound]:
                    if i:
                        float(i)
            except ValueError as error:
                raise ValueError("Value, bounds and units must parse as integers or float") from error

            if (lower_bound and upper_bound) and (float(lower_bound) > float(upper_bound) or float(lower_bound) > float(amount)):
                raise ValueError("Lower bound too large")

            if upper_bound and float(upper_bound) < float(amount):
                raise ValueError("Upper bound too small")

            self.mainsnak.datavalue = {
                'value': {
                    'amount': amount,
                    'unit': unit,
                    'upperBound': upper_bound,
                    'lowerBound': lower_bound
                },
                'type': 'quantity'
            }

            # remove bounds from json if they are undefined
            if not upper_bound:
                del self.mainsnak.datavalue['value']['upperBound']

            if not lower_bound:
                del self.mainsnak.datavalue['value']['lowerBound']

    def from_sparql_value(self, sparql_value: dict) -> Quantity:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: True if the parsing is successful
        """
        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.w3.org/2001/XMLSchema#decimal':
            raise ValueError(f"Wrong SPARQL datatype {datatype}")

        if type != 'literal':
            raise ValueError(f"Wrong SPARQL type {type}")

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            self.set_value(amount=value)

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        return '"' + format_amount(self.mainsnak.datavalue['value']['amount']) + '"^^xsd:decimal'

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        self.set_value(amount=value, unit=unit)
        return True
