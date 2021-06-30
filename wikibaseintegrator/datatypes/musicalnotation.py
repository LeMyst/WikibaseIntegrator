from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class MusicalNotation(BaseDataType):
    """
    Implements the Wikibase data type 'musical-notation'
    """
    DTYPE = 'musical-notation'

    def __init__(self, value, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Values for that data type are strings describing music following LilyPond syntax.
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

        super(MusicalNotation, self).__init__(value=value, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.mainsnak.datavalue = {
            'value': self.value,
            'type': 'string'
        }
