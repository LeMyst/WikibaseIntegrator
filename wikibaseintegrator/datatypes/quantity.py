from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import format_amount


class Quantity(BaseDataType):
    """
    Implements the Wikibase data type for quantities
    """
    DTYPE = 'quantity'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:decimal .
        }}
    '''

    def __init__(self, amount=None, upper_bound=None, lower_bound=None, unit='1', wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param amount: The amount value
        :type amount: float, str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param upper_bound: Upper bound of the value if it exists, e.g. for standard deviations
        :type upper_bound: float, str
        :param lower_bound: Lower bound of the value if it exists, e.g. for standard deviations
        :type lower_bound: float, str
        :param unit: The unit item URL or the QID a certain amount has been measured in (https://www.wikidata.org/wiki/Wikidata:Units).
            The default is dimensionless, represented by a '1'
        :type unit: str
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

        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        unit = unit or '1'

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        if amount:
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

    def get_sparql_value(self):
        return format_amount(self.mainsnak.datavalue['value']['amount'])
