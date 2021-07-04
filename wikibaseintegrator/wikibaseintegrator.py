from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.property import Property
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
        # Use default values from wbi_config
        self.mediawiki_api_url = mediawiki_api_url or config['MEDIAWIKI_API_URL']
        self.mediawiki_index_url = mediawiki_index_url or config['MEDIAWIKI_INDEX_URL']
        self.mediawiki_rest_url = mediawiki_rest_url or config['MEDIAWIKI_REST_URL']
        self.sparql_endpoint_url = sparql_endpoint_url or config['SPARQL_ENDPOINT_URL']
        self.wikibase_url = wikibase_url or config['WIKIBASE_URL']
        self.property_constraint_pid = property_constraint_pid or config['PROPERTY_CONSTRAINT_PID']
        self.distinct_values_constraint_qid = distinct_values_constraint_qid or config['DISTINCT_VALUES_CONSTRAINT_QID']
        self.language = language or config['DEFAULT_LANGUAGE']
        self.lexeme_language = lexeme_language or config['DEFAULT_LEXEME_LANGUAGE']
        self.debug = debug or config['DEBUG']

        # Runtime variables
        self.is_bot = is_bot or False
        self.login = login
        self.search_only = search_only or False

        # Quick access to entities
        self.item = Item(api=self)
        self.property = Property(api=self)
        self.lexeme = Lexeme(api=self)

        # Helpers
        self.helpers = Helpers()
