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
                 login=None,
                 debug=False):
        self.debug = debug

        # Use default values from wbi_config
        mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
        mediawiki_index_url = config['MEDIAWIKI_INDEX_URL'] if mediawiki_index_url is None else mediawiki_index_url
        mediawiki_rest_url = config['MEDIAWIKI_REST_URL'] if mediawiki_rest_url is None else mediawiki_rest_url
        sparql_endpoint_url = config['SPARQL_ENDPOINT_URL'] if sparql_endpoint_url is None else sparql_endpoint_url
        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url
        property_constraint_pid = config['PROPERTY_CONSTRAINT_PID'] if property_constraint_pid is None else property_constraint_pid
        distinct_values_constraint_qid = config['DISTINCT_VALUES_CONSTRAINT_QID'] if distinct_values_constraint_qid is None else distinct_values_constraint_qid
        language = config['DEFAULT_LANGUAGE'] if language is None else language

        self.api = Api(mediawiki_api_url=mediawiki_api_url, mediawiki_index_url=mediawiki_index_url, mediawiki_rest_url=mediawiki_rest_url, sparql_endpoint_url=sparql_endpoint_url,
                       wikibase_url=wikibase_url, property_constraint_pid=property_constraint_pid, distinct_values_constraint_qid=distinct_values_constraint_qid,
                       search_only=search_only, is_bot=is_bot, language=language, login=login, debug=self.debug)

        self.item = Item(api=self.api)
        self.property = Property(api=self.api)
        self.lexeme = Lexeme(api=self.api)
        self.helpers = Helpers()
