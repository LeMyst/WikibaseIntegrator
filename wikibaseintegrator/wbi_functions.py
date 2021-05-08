import datetime
from time import sleep
from warnings import warn

import requests

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import MWApiError, SearchError


def mediawiki_api_call(method, mediawiki_api_url=None, session=None, max_retries=1000, retry_after=60, **kwargs):
    """
    :param method: 'GET' or 'POST'
    :param mediawiki_api_url:
    :param session: If a session is passed, it will be used. Otherwise a new requests session is created
    :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to
    `max_retries` times
    :type max_retries: int
    :param retry_after: Number of seconds to wait before retrying request (see max_retries)
    :type retry_after: int
    :param kwargs: Passed to requests.request
    :return:
    """

    mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url

    # TODO: Add support for 'multipart/form-data' when using POST (https://www.mediawiki.org/wiki/API:Edit#Large_edits)

    if 'data' in kwargs and kwargs['data']:
        if 'format' not in kwargs['data']:
            kwargs['data'].update({'format': 'json'})
        elif kwargs['data']['format'] != 'json':
            raise ValueError("'format' can only be 'json' when using mediawiki_api_call()")

    response = None
    session = session if session else requests.session()
    for n in range(max_retries):
        try:
            response = session.request(method, mediawiki_api_url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            print("Connection error: {}. Sleeping for {} seconds.".format(e, retry_after))
            sleep(retry_after)
            continue
        if response.status_code == 503:
            print("service unavailable. sleeping for {} seconds".format(retry_after))
            sleep(retry_after)
            continue

        response.raise_for_status()
        json_data = response.json()
        """
        Mediawiki api response has code = 200 even if there are errors.
        rate limit doesn't return HTTP 429 either. may in the future
        https://phabricator.wikimedia.org/T172293
        """
        if 'error' in json_data:
            # rate limiting
            error_msg_names = set()
            if 'messages' in json_data['error']:
                error_msg_names = set(x.get('name') for x in json_data['error']['messages'])
            if 'actionthrottledtext' in error_msg_names:
                sleep_sec = int(response.headers.get('retry-after', retry_after))
                print("{}: rate limited. sleeping for {} seconds".format(datetime.datetime.utcnow(), sleep_sec))
                sleep(sleep_sec)
                continue

            # maxlag
            if 'code' in json_data['error'] and json_data['error']['code'] == 'maxlag':
                sleep_sec = json_data['error'].get('lag', retry_after)
                print("{}: maxlag. sleeping for {} seconds".format(datetime.datetime.utcnow(), sleep_sec))
                sleep(sleep_sec)
                continue

            # readonly
            if 'code' in json_data['error'] and json_data['error']['code'] == 'readonly':
                print('The Wikibase instance is currently in readonly mode, waiting for {} seconds'.format(retry_after))
                sleep(retry_after)
                continue

            # others case
            raise MWApiError(response.json() if response else {})

        # there is no error or waiting. break out of this loop and parse response
        break
    else:
        # the first time I've ever used for - else!!
        # else executes if the for loop completes normally. i.e. does not encouter a `break`
        # in this case, that means it tried this api call 10 times
        raise MWApiError(response.json() if response else {})

    return json_data


def mediawiki_api_call_helper(data, login=None, mediawiki_api_url=None, user_agent=None, allow_anonymous=False, max_retries=1000, retry_after=60):
    mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
    user_agent = config['USER_AGENT_DEFAULT'] if user_agent is None else user_agent

    if not allow_anonymous:
        if login is None:
            # Force allow_anonymous as False by default to ask for a login object
            raise ValueError("allow_anonymous can't be False and login is None at the same time.")
        elif mediawiki_api_url != login.mediawiki_api_url:
            raise ValueError("mediawiki_api_url can't be different with the one in the login object.")

    headers = {
        'User-Agent': user_agent
    }

    if data is not None:
        if login is not None and 'token' not in data:
            data.update({'token': login.get_edit_token()})

        if not allow_anonymous:
            # Always assert user if allow_anonymous is False
            if 'assert' not in data:
                data.update({'assert': 'user'})
            if 'token' in data and data['token'] == '+\\':
                raise wbi_login.LoginError("Anonymous edit are not allowed by default. Set allow_anonymous to True to edit mediawiki anonymously.")
        elif 'assert' not in data:
            # Always assert anon if allow_anonymous is True
            data.update({'assert': 'anon'})

    login_session = login.get_session() if login is not None else None

    return mediawiki_api_call('POST', mediawiki_api_url, login_session, data=data, headers=headers, max_retries=max_retries, retry_after=retry_after)


@wbi_backoff()
def execute_sparql_query(query, prefix=None, endpoint=None, user_agent=None, max_retries=1000, retry_after=60, debug=False):
    """
    Static method which can be used to execute any SPARQL query
    :param prefix: The URI prefixes required for an endpoint, default is the Wikidata specific prefixes
    :param query: The actual SPARQL query string
    :param endpoint: The URL string for the SPARQL endpoint. Default is the URL for the Wikidata SPARQL endpoint
    :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
    :type user_agent: str
    :param max_retries: The number time this function should retry in case of header reports.
    :param retry_after: the number of seconds should wait upon receiving either an error code or the Query Service is not reachable.
    :param debug: Enable debug output.
    :type debug: boolean
    :return: The results of the query are returned in JSON format
    """

    sparql_endpoint_url = config['SPARQL_ENDPOINT_URL'] if endpoint is None else endpoint
    user_agent = config['USER_AGENT_DEFAULT'] if user_agent is None else user_agent

    if prefix:
        query = prefix + '\n' + query

    params = {
        'query': '#Tool: WikibaseIntegrator wbi_functions.execute_sparql_query\n' + query,
        'format': 'json'
    }

    headers = {
        'Accept': 'application/sparql-results+json',
        'User-Agent': user_agent
    }

    if debug:
        print(params['query'])

    for n in range(max_retries):
        try:
            response = requests.post(sparql_endpoint_url, params=params, headers=headers)
        except requests.exceptions.ConnectionError as e:
            print("Connection error: {}. Sleeping for {} seconds.".format(e, retry_after))
            sleep(retry_after)
            continue
        if response.status_code == 503:
            print("Service unavailable (503). Sleeping for {} seconds".format(retry_after))
            sleep(retry_after)
            continue
        if response.status_code == 429:
            if 'retry-after' in response.headers.keys():
                retry_after = response.headers['retry-after']
            print("Too Many Requests (429). Sleeping for {} seconds".format(retry_after))
            sleep(retry_after)
            continue
        response.raise_for_status()
        results = response.json()

        return results


def merge_items(from_id, to_id, ignore_conflicts='', mediawiki_api_url=None, login=None, allow_anonymous=False, user_agent=None):
    """
    A static method to merge two items
    :param from_id: The QID which should be merged into another item
    :type from_id: string with 'Q' prefix
    :param to_id: The QID into which another item should be merged
    :type to_id: string with 'Q' prefix
    :param mediawiki_api_url: The MediaWiki url which should be used
    :type mediawiki_api_url: str
    :param ignore_conflicts: A string with the values 'description', 'statement' or 'sitelink', separated by a pipe ('|') if using more than one of those.
    :type ignore_conflicts: str
    :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :type allow_anonymous: bool
    :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
    :type user_agent: str
    """

    params = {
        'action': 'wbmergeitems',
        'fromid': from_id,
        'toid': to_id,
        'format': 'json',
        'bot': '',
        'ignoreconflicts': ignore_conflicts
    }

    if config['MAXLAG'] > 0:
        params.update({'maxlag': config['MAXLAG']})

    return mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)


def remove_claims(claim_id, summary=None, revision=None, mediawiki_api_url=None, login=None, allow_anonymous=False, user_agent=None):
    """
    Delete an item
    :param claim_id: One GUID or several (pipe-separated) GUIDs identifying the claims to be removed. All claims must belong to the same entity.
    :type claim_id: string
    :param summary: Summary for the edit. Will be prepended by an automatically generated comment.
    :type summary: str
    :param revision: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
    :type revision: str
    :param mediawiki_api_url: The MediaWiki url which should be used
    :type mediawiki_api_url: str
    :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :type allow_anonymous: bool
    :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
    :type user_agent: str
    """

    params = {
        'action': 'wbremoveclaims',
        'claim': claim_id,
        'summary': summary,
        'baserevid': revision,
        'bot': True,
        'format': 'json'
    }

    if config['MAXLAG'] > 0:
        params.update({'maxlag': config['MAXLAG']})

    return mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)


def search_entities(search_string, language=None, strict_language=True, search_type='item', mediawiki_api_url=None, max_results=500, dict_result=False, login=None,
                    allow_anonymous=True, user_agent=None):
    """
    Performs a search for entities in the Wikibase instance using labels and aliases.
    :param search_string: a string which should be searched for in the Wikibase instance (labels and aliases)
    :type search_string: str
    :param language: The language in which to perform the search.
    :type language: str
    :param strict_language: Whether to disable language fallback
    :type strict_language: bool
    :param search_type: Search for this type of entity. One of the following values: form, item, lexeme, property, sense
    :type search_type: str
    :param mediawiki_api_url: Specify the mediawiki_api_url.
    :type mediawiki_api_url: str
    :param max_results: The maximum number of search results returned. Default 500
    :type max_results: int
    :param dict_result:
    :type dict_result: boolean
    :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :type allow_anonymous: bool
    :param user_agent: The user agent string transmitted in the http header
    :type user_agent: str
    :return: list
    """

    language = config['DEFAULT_LANGUAGE'] if language is None else language

    params = {
        'action': 'wbsearchentities',
        'search': search_string,
        'language': language,
        'strict_language': strict_language,
        'type': search_type,
        'limit': 50,
        'format': 'json'
    }

    cont_count = 0
    results = []

    while True:
        params.update({'continue': cont_count})

        search_results = mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent,
                                                   allow_anonymous=allow_anonymous)

        if search_results['success'] != 1:
            raise SearchError('Wikibase API wbsearchentities failed')
        else:
            for i in search_results['search']:
                if dict_result:
                    description = i['description'] if 'description' in i else None
                    aliases = i['aliases'] if 'aliases' in i else None
                    results.append({
                        'id': i['id'],
                        'label': i['label'],
                        'match': i['match'],
                        'description': description,
                        'aliases': aliases
                    })
                else:
                    results.append(i['id'])

        if 'search-continue' not in search_results:
            break
        else:
            cont_count = search_results['search-continue']

        if cont_count >= max_results:
            break

    return results


def generate_item_instances(items, mediawiki_api_url=None, login=None, allow_anonymous=True, user_agent=None):
    """
    A method which allows for retrieval of a list of Wikidata items or properties. The method generates a list of
    tuples where the first value in the tuple is the QID or property ID, whereas the second is the new instance of
    ItemEngine containing all the data of the item. This is most useful for mass retrieval of items.
    :param user_agent: A custom user agent
    :type user_agent: str
    :param items: A list of QIDs or property IDs
    :type items: list
    :param mediawiki_api_url: The MediaWiki url which should be used
    :type mediawiki_api_url: str
    :return: A list of tuples, first value in the tuple is the QID or property ID string, second value is the instance of ItemEngine with the corresponding
        item data.
    :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :type allow_anonymous: bool
    """

    assert type(items) == list

    from wikibaseintegrator.wbi_core import ItemEngine

    params = {
        'action': 'wbgetentities',
        'ids': '|'.join(items),
        'format': 'json'
    }

    reply = mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

    item_instances = []
    for qid, v in reply['entities'].items():
        ii = ItemEngine(item_id=qid, item_data=v)
        ii.mediawiki_api_url = mediawiki_api_url
        item_instances.append((qid, ii))

    return item_instances


def get_distinct_value_props(sparql_endpoint_url=None, wikibase_url=None, property_constraint_pid=None, distinct_values_constraint_qid=None):
    """
    On wikidata, the default core IDs will be the properties with a distinct values constraint select ?p where {?p wdt:P2302 wd:Q21502410}
    See: https://www.wikidata.org/wiki/Help:Property_constraints_portal
    https://www.wikidata.org/wiki/Help:Property_constraints_portal/Unique_value
    """

    wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url
    property_constraint_pid = config['PROPERTY_CONSTRAINT_PID'] if property_constraint_pid is None else property_constraint_pid
    distinct_values_constraint_qid = config['DISTINCT_VALUES_CONSTRAINT_QID'] if distinct_values_constraint_qid is None else distinct_values_constraint_qid

    pcpid = property_constraint_pid
    dvcqid = distinct_values_constraint_qid

    query = '''
        SELECT ?p WHERE {{
            ?p <{wb_url}/prop/direct/{prop_nr}> <{wb_url}/entity/{entity}>
        }}
        '''.format(wb_url=wikibase_url, prop_nr=pcpid, entity=dvcqid)
    results = execute_sparql_query(query, endpoint=sparql_endpoint_url)['results']['bindings']
    if not results:
        warn("Warning: No distinct value properties found\n" +
             "Please set P2302 and Q21502410 in your Wikibase or set `core_props` manually.\n" +
             "Continuing with no core_props")
        return set()
    else:
        return set(map(lambda x: x['p']['value'].rsplit('/', 1)[-1], results))
