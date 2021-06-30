from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.property import Property
from wikibaseintegrator.wbi_api import Api
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_helpers import Helpers


class WikibaseIntegrator(object):
    def __init__(self,
                 mediawiki_api_url=None,
                 mediawiki_index_url=None,
                 mediawiki_rest_url=None,
                 sparql_endpoint_url=None,
                 wikibase_url=None,
                 property_constraint_pid=None,
                 distinct_values_constraint_qid=None,
                 search_only=False,
                 is_bot=False,
                 language=None,
                 lexeme_language=None,
                 login=None,
                 debug=False):
        self.debug = debug

        # Use default values from wbi_config
        mediawiki_api_url = mediawiki_api_url or config['MEDIAWIKI_API_URL']
        mediawiki_index_url = mediawiki_index_url or config['MEDIAWIKI_INDEX_URL']
        mediawiki_rest_url = mediawiki_rest_url or config['MEDIAWIKI_REST_URL']
        sparql_endpoint_url = sparql_endpoint_url or config['SPARQL_ENDPOINT_URL']
        wikibase_url = wikibase_url or config['WIKIBASE_URL']
        property_constraint_pid = property_constraint_pid or config['PROPERTY_CONSTRAINT_PID']
        distinct_values_constraint_qid = distinct_values_constraint_qid or config['DISTINCT_VALUES_CONSTRAINT_QID']
        language = language or config['DEFAULT_LANGUAGE']
        lexeme_language = lexeme_language or config['DEFAULT_LEXEME_LANGUAGE']

        self.api = Api(mediawiki_api_url=mediawiki_api_url, mediawiki_index_url=mediawiki_index_url, mediawiki_rest_url=mediawiki_rest_url, sparql_endpoint_url=sparql_endpoint_url,
                       wikibase_url=wikibase_url, property_constraint_pid=property_constraint_pid, distinct_values_constraint_qid=distinct_values_constraint_qid,
                       search_only=search_only, is_bot=is_bot, language=language, lexeme_language=lexeme_language, login=login, debug=self.debug)

        self.item = Item(api=self.api)
        self.property = Property(api=self.api)
        self.lexeme = Lexeme(api=self.api)
        self.helpers = Helpers()
