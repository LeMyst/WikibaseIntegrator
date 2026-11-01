from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType

# A number as written by Python or by a user: an optional sign, digits with an optional fraction, an optional exponent. No
# whitespace, nan or infinity, which Wikibase doesn't accept either.
NUMBER_PATTERN = re.compile(r'^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$')


# Here rather than in wbi_helpers (which re-exports it): the data types don't depend on the HTTP layer
def format_amount(amount: int | str | float) -> str:
    """
    A formatting function mostly used for Quantity datatype.

    The amount is formatted like the decimals of Wikibase: a sign, the digits without exponent, and no fraction for an
    integer (42.0 is +42). The digits of a string or an int are kept as they are: a large number is not rounded like a float.

    :param amount: A int, float or str you want to pass to Quantity value.
    :return: A correctly formatted string amount by Wikibase standard.
    :raises ValueError: When the amount is not a finite number.
    """
    # str() of a float is its shortest representation, e.g. 1e-05: the binary noise of the float isn't kept
    text = str(amount)
    if isinstance(amount, bool) or not NUMBER_PATTERN.match(text):
        raise ValueError(f"The amount {amount!r} is not a finite number")

    number = Decimal(text)
    if number.is_zero():
        return '+0'

    # Remove the fraction of an integer, e.g. 42.0, and write the exponent as digits, e.g. 1.5e-5 is 0.000015
    digits = format(number, 'f')
    if number == number.to_integral_value():
        digits = digits.split('.', 1)[0]

    # Adding prefix + for positive number
    return digits if digits.startswith('-') else f'+{digits}'


class Quantity(BaseDataType):
    """
    Implements the Wikibase data type for quantities
    """
    DTYPE = WikibaseDatatype.QUANTITY
    PTYPE = 'http://wikiba.se/ontology#Quantity'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:decimal .
        }}
    '''

    def __init__(self, amount: str | int | float | None = None, upper_bound: str | int | float | None = None, lower_bound: str | int | float | None = None, unit: str | int = '1',
                 wikibase_url: str | None = None, **kwargs: Any) -> None:
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

    # The keyword arguments of this public method are named after the parts of the value, not 'value' like in BaseDataType
    # pylint: disable-next=arguments-renamed
    def set_value(self, amount: str | int | float | None = None, upper_bound: str | int | float | None = None, lower_bound: str | int | float | None = None, unit: str | int = '1',
                  wikibase_url: str | None = None) -> None:
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        unit = str(unit or '1')

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        if amount is not None:
            unit = str(unit)
            # A bound of 0 is a bound: only None (or an empty string) is no bound
            if upper_bound == '':
                upper_bound = None
            if lower_bound == '':
                lower_bound = None

            # Integrity checks for value and bounds
            try:
                amount = format_amount(amount)
                if upper_bound is not None:
                    upper_bound = format_amount(upper_bound)
                if lower_bound is not None:
                    lower_bound = format_amount(lower_bound)
            except ValueError as error:
                raise ValueError("Value, bounds and units must parse as integers or float") from error

            # Compared as Decimal, without the rounding of float
            if (lower_bound is not None and upper_bound is not None) and (Decimal(lower_bound) > Decimal(upper_bound) or Decimal(lower_bound) > Decimal(amount)):
                raise ValueError("Lower bound too large")

            if upper_bound is not None and Decimal(upper_bound) < Decimal(amount):
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
            if upper_bound is None:
                del self.mainsnak.datavalue['value']['upperBound']

            if lower_bound is None:
                del self.mainsnak.datavalue['value']['lowerBound']

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: True if the parsing is successful
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.w3.org/2001/XMLSchema#decimal':
            raise ValueError(f"Wrong SPARQL datatype {datatype}")

        if type != 'literal':
            raise ValueError(f"Wrong SPARQL type {type}")

        self.set_value(amount=value)

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        return '"' + format_amount(self.mainsnak.datavalue['value']['amount']) + '"^^xsd:decimal'

    def parse_sparql_value(self, value: str, type: str = 'literal', unit: str = '1') -> bool:
        self.set_value(amount=value, unit=unit)
        return True
