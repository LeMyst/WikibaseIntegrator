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

    def __init__(self, text: str = None, language: str = None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param text: The language specific string to be used as the value.
        :param language: Specifies the language the value belongs to.
        """

        super().__init__(**kwargs)

        language = language or config['DEFAULT_LANGUAGE']

        assert isinstance(text, str) or text is None, f"Expected str, found {type(text)} ({text})"
        assert isinstance(language, str), f"Expected str, found {type(language)} ({language})"

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
