from wikibaseintegrator.wbi_core import Core
from wikibaseintegrator.wbi_item import Item
from wikibaseintegrator.wbi_lexeme import Lexeme
from wikibaseintegrator.wbi_property import Property

DEFAULT_CONFIG = {
    'BACKOFF_MAX_TRIES': None,
    'BACKOFF_MAX_VALUE': 3600,
    'USER_AGENT_DEFAULT': "WikibaseIntegrator/{} (https://github.com/LeMyst/WikibaseIntegrator)".format(__version__),
    'MAXLAG': 5,
    'PROPERTY_CONSTRAINT_PID': 'P2302',
    'DISTINCT_VALUES_CONSTRAINT_QID': 'Q21502410',
    'COORDINATE_GLOBE_QID': 'http://www.wikidata.org/entity/Q2',
    'CALENDAR_MODEL_QID': 'http://www.wikidata.org/entity/Q1985727',
    'MEDIAWIKI_API_URL': 'https://www.wikidata.org/w/api.php',
    'MEDIAWIKI_INDEX_URL': 'https://www.wikidata.org/w/index.php',
    'MEDIAWIKI_REST_URL': 'https://www.wikidata.org/w/rest.php',
    'SPARQL_ENDPOINT_URL': 'https://query.wikidata.org/sparql',
    'WIKIBASE_URL': 'http://www.wikidata.org',
    'LANGUAGE': 'en'
}


class WikibaseIntegrator(object):
    def __init__(self,
                 mediawiki_api_url=DEFAULT_CONFIG["MEDIAWIKI_API_URL"],
                 mediawiki_index_url=DEFAULT_CONFIG["MEDIAWIKI_INDEX_URL"],
                 mediawiki_rest_url=DEFAULT_CONFIG["MEDIAWIKI_REST_URL"],
                 sparql_endpoint_url=DEFAULT_CONFIG["MEDIAWIKI_API_URL"],
                 wikibase_url=DEFAULT_CONFIG["WIKIBASE_URL"],
                 is_bot=False,
                 language=DEFAULT_CONFIG["LANGUAGE"]):
        core = Core()

        self.core = core

        self.item = Item(core)
        self.property = Property(core)
        self.lexeme = Lexeme(core)
