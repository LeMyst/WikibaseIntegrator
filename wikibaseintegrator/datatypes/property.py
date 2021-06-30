import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class Property(BaseDataType):
    """
    Implements the Wikibase data type 'property'
    """
    DTYPE = 'wikibase-property'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/P{value}> .
        }}
    '''

    def __init__(self, value, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The property number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
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

        super(Property, self).__init__(**kwargs)

        assert isinstance(value, (str, int)) or value is None, "Expected str or int, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid property ID ({}), format must be 'P[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.mainsnak.datavalue = {
            'value': {
                'entity-type': 'property',
                'numeric-id': self.value,
                'id': 'P{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }
