from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_jsonparser import JsonParser


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

    def __init__(self, quantity, prop_nr, upper_bound=None, lower_bound=None, unit='1', wikibase_url=None, **kwargs):
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
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        self.quantity = None
        self.unit = None
        self.upper_bound = None
        self.lower_bound = None

        value = (quantity, unit, upper_bound, lower_bound)

        super(Quantity, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        self.quantity, self.unit, self.upper_bound, self.lower_bound = value

        if self.quantity is not None:
            self.quantity = self.format_amount(self.quantity)
            self.unit = str(self.unit)
            if self.upper_bound:
                self.upper_bound = self.format_amount(self.upper_bound)
            if self.lower_bound:
                self.lower_bound = self.format_amount(self.lower_bound)

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
        elif self.snaktype == 'value':
            raise ValueError("Parameter 'quantity' can't be 'None' if 'snaktype' is 'value'")

        self.json_representation['datavalue'] = {
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
            del self.json_representation['datavalue']['value']['upperBound']

        if not self.lower_bound:
            del self.json_representation['datavalue']['value']['lowerBound']

        self.value = (self.quantity, self.unit, self.upper_bound, self.lower_bound)
        super(Quantity, self).set_value(value=self.value)

    def get_sparql_value(self):
        return self.quantity

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(quantity=None, prop_nr=jsn['property'], snaktype=jsn['snaktype'])

        value = jsn['datavalue']['value']
        upper_bound = value['upperBound'] if 'upperBound' in value else None
        lower_bound = value['lowerBound'] if 'lowerBound' in value else None
        return cls(quantity=value['amount'], prop_nr=jsn['property'], upper_bound=upper_bound, lower_bound=lower_bound, unit=value['unit'])

    @staticmethod
    def format_amount(amount):
        # Remove .0 by casting to int
        if float(amount) % 1 == 0:
            amount = int(float(amount))

        # Adding prefix + for positive number and 0
        if not str(amount).startswith('+') and float(amount) >= 0:
            amount = str('+{}'.format(amount))

        # return as string
        return str(amount)
