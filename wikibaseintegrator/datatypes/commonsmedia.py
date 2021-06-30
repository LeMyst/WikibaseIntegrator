from wikibaseintegrator.datatypes.basedatatype import BaseDataType


class CommonsMedia(BaseDataType):
    """
    Implements the Wikibase data type for Wikimedia commons media files
    """
    DTYPE = 'commonsMedia'

    def __init__(self, value, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The media file name from Wikimedia commons to be used as the value
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

        self.value = None

        super(CommonsMedia, self).__init__(value=value, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.mainsnak.datavalue = {
            'value': self.value,
            'type': 'string'
        }
