import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class TabularData(BaseDataType):
    """
    Implements the Wikibase data type 'tabular-data'
    """
    DTYPE = 'tabular-data'

    def __init__(self, value=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Reference to tabular data file on Wikimedia Commons.
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
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

        super(TabularData, self).__init__(**kwargs)

        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)

        if value:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Taipei+Population.tab
            pattern = re.compile(r'^Data:((?![:|#]).)+\.tab$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .tab. In addition title should not contain characters like colon, hash or pipe.")

            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
