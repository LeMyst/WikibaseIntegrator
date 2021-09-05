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

    def __init__(self, text=None, language=None, **kwargs):
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

        language = language or config['DEFAULT_LANGUAGE']

        assert isinstance(text, str) or text is None, "Expected str, found {} ({})".format(type(text), text)
        assert isinstance(language, str), "Expected str, found {} ({})".format(type(language), language)

        if text and language:
            self.mainsnak.datavalue = {
                'value': {
                    'text': text,
                    'language': language
                },
                'type': 'monolingualtext'
            }

    def get_sparql_value(self):
        return '"' + self.mainsnak.datavalue['value']['text'].replace('"', r'\"') + '"@' + self.mainsnak.datavalue['value']['language']
