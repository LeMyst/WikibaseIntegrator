from wikibaseintegrator.wbi_api import Api
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.entities.item import Item
from wikibaseintegrator.entities.lexeme import Lexeme
from wikibaseintegrator.entities.property import Property


class WikibaseIntegrator(object):
    def __init__(self,
                 mediawiki_api_url=config["MEDIAWIKI_API_URL"],
                 mediawiki_index_url=config["MEDIAWIKI_INDEX_URL"],
                 mediawiki_rest_url=config["MEDIAWIKI_REST_URL"],
                 sparql_endpoint_url=config["SPARQL_ENDPOINT_URL"],
                 wikibase_url=config["WIKIBASE_URL"],
                 property_constraint_pid=config["PROPERTY_CONSTRAINT_PID"],
                 distinct_values_constraint_qid=config["DISTINCT_VALUES_CONSTRAINT_QID"],
                 search_only=False,
                 fast_run=False,
                 fast_run_base_filter=None,
                 fast_run_use_refs=False,
                 fast_run_case_insensitive=False,
                 is_bot=False,
                 language=config["DEFAULT_LANGUAGE"],
                 login=None,
                 debug=False):
        self.debug = debug
        self.api = Api(mediawiki_api_url=mediawiki_api_url, mediawiki_index_url=mediawiki_index_url, mediawiki_rest_url=mediawiki_rest_url, sparql_endpoint_url=sparql_endpoint_url,
                       wikibase_url=wikibase_url, property_constraint_pid=property_constraint_pid, distinct_values_constraint_qid=distinct_values_constraint_qid,
                       search_only=search_only, fast_run=fast_run, fast_run_base_filter=fast_run_base_filter, fast_run_use_refs=fast_run_use_refs,
                       fast_run_case_insensitive=fast_run_case_insensitive, is_bot=is_bot, language=language, login=login, debug=self.debug)

        self.item = Item(api=self.api)
        self.property = Property(api=self.api)
        self.lexeme = Lexeme(api=self.api)
        # self.functions = Functions()
