from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_jsonparser import JsonParser


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

    def __init__(self, text, prop_nr, language=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param text: The language specific string to be used as the value
        :type text: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param language: Specifies the language the value belongs to
        :type language: str
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

        self.text = None
        self.language = config['DEFAULT_LANGUAGE'] if language is None else language

        value = (text, self.language)

        super(MonolingualText, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        self.text, self.language = value
        if self.text is not None:
            assert isinstance(self.text, str) or self.text is None, "Expected str, found {} ({})".format(type(self.text), self.text)
        elif self.snaktype == 'value':
            raise ValueError("Parameter 'text' can't be 'None' if 'snaktype' is 'value'")
        assert isinstance(self.language, str), "Expected str, found {} ({})".format(type(self.language), self.language)

        self.json_representation['datavalue'] = {
            'value': {
                'text': self.text,
                'language': self.language
            },
            'type': 'monolingualtext'
        }

        self.value = (self.text, self.language)
        super(MonolingualText, self).set_value(value=self.value)

    def get_sparql_value(self):
        return '"' + self.text.replace('"', r'\"') + '"@' + self.language

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(text=None, prop_nr=jsn['property'], snaktype=jsn['snaktype'])

        value = jsn['datavalue']['value']
        return cls(text=value['text'], prop_nr=jsn['property'], language=value['language'])
