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

    def __init__(self, quantity, upper_bound=None, lower_bound=None, unit='1', wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param quantity: The quantity value
        :type quantity: float, str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param upper_bound: Upper bound of the value if it exists, e.g. for standard deviations
        :type upper_bound: float, str
        :param lower_bound: Lower bound of the value if it exists, e.g. for standard deviations
        :type lower_bound: float, str
        :param unit: The unit item URL or the QID a certain quantity has been measured in (https://www.wikidata.org/wiki/Wikidata:Units).
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

        super(Quantity, self).__init__(**kwargs)

        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        self.quantity = None
        self.unit = None
        self.upper_bound = None
        self.lower_bound = None

        value = (quantity, unit, upper_bound, lower_bound)

        self.quantity, self.unit, self.upper_bound, self.lower_bound = value

        if self.quantity is not None:
            self.quantity = format_amount(self.quantity)
            self.unit = str(self.unit)
            if self.upper_bound:
                self.upper_bound = format_amount(self.upper_bound)
            if self.lower_bound:
                self.lower_bound = format_amount(self.lower_bound)

            # Integrity checks for value and bounds
            try:
                for i in [self.quantity, self.upper_bound, self.lower_bound]:
                    if i:
                        float(i)
            except ValueError:
                raise ValueError("Value, bounds and units must parse as integers or float")

            if (self.lower_bound and self.upper_bound) and (float(self.lower_bound) > float(self.upper_bound)
                                                            or float(self.lower_bound) > float(self.quantity)):
                raise ValueError("Lower bound too large")

            if self.upper_bound and float(self.upper_bound) < float(self.quantity):
                raise ValueError("Upper bound too small")

        self.mainsnak.datavalue = {
            'value': {
                'amount': self.quantity,
                'unit': self.unit,
                'upperBound': self.upper_bound,
                'lowerBound': self.lower_bound
            },
            'type': 'quantity'
        }

        # remove bounds from json if they are undefined
        if not self.upper_bound:
            del self.mainsnak.datavalue['value']['upperBound']

        if not self.lower_bound:
            del self.mainsnak.datavalue['value']['lowerBound']

        self.value = (self.quantity, self.unit, self.upper_bound, self.lower_bound)

    def get_sparql_value(self):
        return format_amount(self.quantity)
