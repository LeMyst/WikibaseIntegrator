from __future__ import annotations

import re
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseSnakType


class MonolingualText(BaseDataType):
    """
    Implements the Wikibase data type for Monolingual Text strings
    """
    DTYPE = 'monolingualtext'
    PTYPE = 'http://wikiba.se/ontology#Monolingualtext'

    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> {value} .
        }}
    '''

    def __init__(self, text: str | None = None, language: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param text: The language specific string to be used as the value.
        :param language: Specifies the language the value belongs to.
        """

        super().__init__(**kwargs)
        self.set_value(text=text, language=language)

    def set_value(self, text: str | None = None, language: str | None = None):
        language = language or str(config['DEFAULT_LANGUAGE'])

        assert isinstance(text, str) or text is None, f"Expected str, found {type(text)} ({text})"
        assert isinstance(language, str), f"Expected str, found {type(language)} ({language})"

        if text and ('\n' in text or '\r' in text):
            raise ValueError("MonolingualText text must not contain newline character")

        if text and language:
            self.mainsnak.datavalue = {
                'value': {
                    'text': text,
                    'language': language
                },
                'type': 'monolingualtext'
            }

    def from_sparql_value(self, sparql_value: dict) -> MonolingualText:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of datatype, type and value
        :return: True if the parsing is successful
        """
        xml_lang = sparql_value['xml:lang']
        type = sparql_value['type']
        value = sparql_value['value']

        if type != 'literal':
            raise ValueError(f"Wrong SPARQL type {type}")

        if value.startswith('http://www.wikidata.org/.well-known/genid/'):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
        else:
            self.set_value(text=value, language=xml_lang)

        return self

    def get_sparql_value(self, **kwargs: Any) -> str:
        return '"' + self.mainsnak.datavalue['value']['text'].replace('"', r'\"') + '"@' + self.mainsnak.datavalue['value']['language']

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^"(.*?)"@([a-z\-]*)$')
        matches = pattern.match(value)
        if not matches:
            return False

        self.set_value(text=matches.group(1), language=matches.group(2))
        return True
