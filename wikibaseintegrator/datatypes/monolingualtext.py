from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config


class MonolingualText(BaseDataType):
    """
    Implements the Wikibase data type for Monolingual Text strings
    """
    DTYPE = 'monolingualtext'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> {value} .
        }}
    '''

    def __init__(self, text, language=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param text: The language specific string to be used as the value
        :type text: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param language: Specifies the language the value belongs to
        :type language: str
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(MonolingualText, self).__init__(**kwargs)

        self.text = None
        self.language = language or config['DEFAULT_LANGUAGE']

        value = (text, self.language)

        self.text, self.language = value
        if self.text is not None:
            assert isinstance(self.text, str) or self.text is None, "Expected str, found {} ({})".format(type(self.text), self.text)
        elif self.mainsnak.snaktype == 'value':
            raise ValueError("Parameter 'text' can't be 'None' if 'snaktype' is 'value'")
        assert isinstance(self.language, str), "Expected str, found {} ({})".format(type(self.language), self.language)

        self.mainsnak.datavalue = {
            'value': {
                'text': self.text,
                'language': self.language
            },
            'type': 'monolingualtext'
        }

        self.value = (self.text, self.language)

    def get_sparql_value(self):
        return '"' + self.text.replace('"', r'\"') + '"@' + self.language
