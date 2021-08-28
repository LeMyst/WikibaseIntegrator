from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class String(BaseDataType):
    """
    Implements the Wikibase data type 'string'
    """

    DTYPE = 'string'

    def __init__(self, value=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The string to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
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

        super(String, self).__init__(**kwargs)

        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)

        if value:
            self.mainsnak.datavalue = {
                'value': value,
                'type': 'string'
            }
