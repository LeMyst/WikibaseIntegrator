import datetime
from time import sleep
from urllib.parse import urlparse

import requests

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import MWApiError, SearchError


def mediawiki_api_call(method, mediawiki_api_url=None, session=None, max_retries=1000, retry_after=60, **kwargs):
    """
    :param method: 'GET' or 'POST'
    :param mediawiki_api_url:
    :param session: If a session is passed, it will be used. Otherwise a new requests session is created
    :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to `max_retries` times
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
    session = session if session else requests.Session()
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
                # We multiply the number of second by the number of tries
                sleep_sec *= n + 1
                # The number of second can't be less than 5
                sleep_sec = max(sleep_sec, 5)
                # The number of second can't be more than retry_after
                sleep_sec = min(sleep_sec, retry_after)
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


def mediawiki_api_call_helper(data, login=None, mediawiki_api_url=None, user_agent=None, allow_anonymous=False, max_retries=1000, retry_after=60, is_bot=False):
    mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
    user_agent = config['USER_AGENT'] if user_agent is None else user_agent

    if urlparse(mediawiki_api_url).hostname.endswith(('wikidata.org', 'wikipedia.org', 'wikimedia.org')) and user_agent is None:
        print('WARNING: Please set an user agent if you interact with a Wikibase instance from the Wikimedia Foundation.')
        print('More information in the README.md and https://meta.wikimedia.org/wiki/User-Agent_policy')

    if not allow_anonymous:
        if login is None:
            # Force allow_anonymous as False by default to ask for a login object
            raise ValueError("allow_anonymous can't be False and login is None at the same time.")
        elif mediawiki_api_url != login.mediawiki_api_url:
            raise ValueError("mediawiki_api_url can't be different with the one in the login object.")

    headers = {
        'User-Agent': get_user_agent(user_agent, login.user if login else None)
    }

    if data is not None:
        if login is not None and 'token' not in data:
            data.update({'token': login.get_edit_token()})
        elif 'token' not in data:
            data.update({'token': '+\\'})

        if not allow_anonymous:
            # Always assert user if allow_anonymous is False
            if 'assert' not in data:
                if is_bot:
                    data.update({'assert': 'bot'})
                else:
                    data.update({'assert': 'user'})
            if 'token' in data and data['token'] == '+\\':
                raise Exception("Anonymous edit are not allowed by default. "
                                "Set allow_anonymous to True to edit mediawiki anonymously or set the login parameter with a valid Login object.")
        elif 'assert' not in data:
            # Always assert anon if allow_anonymous is True
            data.update({'assert': 'anon'})

        if config['MAXLAG'] > 0:
            data.update({'maxlag': config['MAXLAG']})

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
    user_agent = (config['USER_AGENT'] if user_agent is None else user_agent)

    if urlparse(endpoint).hostname.endswith(('wikidata.org', 'wikipedia.org', 'wikimedia.org')) and user_agent is None:
        print('WARNING: Please set an user agent if you interact with a Wikibase instance from the Wikimedia Foundation.')
        print('More information in the README.md and https://meta.wikimedia.org/wiki/User-Agent_policy')

    if prefix:
        query = prefix + '\n' + query

    params = {
        'query': '#Tool: WikibaseIntegrator wbi_functions.execute_sparql_query\n' + query,
        'format': 'json'
    }

    headers = {
        'Accept': 'application/sparql-results+json',
        'User-Agent': get_user_agent(user_agent),
        'Content-Type': 'multipart/form-data'
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


def merge_items(from_id, to_id, ignore_conflicts='', **kwargs):
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

    return mediawiki_api_call_helper(data=params, **kwargs)


def merge_lexemes(source, target, summary=None, **kwargs):
    """
    A static method to merge two items

    :param source: The QID which should be merged into another item
    :type source: string with 'Q' prefix
    :param target: The QID into which another item should be merged
    :type target: string with 'Q' prefix
    """

    params = {
        'action': 'wblmergelexemes',
        'fromid': source,
        'toid': target,
        'format': 'json',
        'bot': ''
    }

    if summary:
        params.update({'summary': summary})

    return mediawiki_api_call_helper(data=params, **kwargs)


def remove_claims(claim_id, summary=None, revision=None, **kwargs):
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
        'bot': '',
        'format': 'json'
    }

    if summary:
        params.update({'summary': summary})

    if revision:
        params.update({'revision': revision})

    return mediawiki_api_call_helper(data=params, **kwargs)


def search_entities(search_string, language=None, strict_language=True, search_type='item', max_results=500, dict_result=False, allow_anonymous=True, **kwargs):
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

        search_results = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)

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


def generate_entity_instances(entities, allow_anonymous=True, **kwargs):
    """
    A method which allows for retrieval of a list of Wikidata entities. The method generates a list of tuples where the first value in the tuple is the entity's ID, whereas the
    second is the new instance of a subclass of BaseEntity containing all the data of the entity. This is most useful for mass retrieval of entities.
    :param user_agent: A custom user agent
    :type user_agent: str
    :param entities: A list of IDs. Item, Property or Lexeme.
    :type entities: list
    :param mediawiki_api_url: The MediaWiki url which should be used
    :type mediawiki_api_url: str
    :return: A list of tuples, first value in the tuple is the entity's ID, second value is the instance of a subclass of BaseEntity with the corresponding entity data.
    :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :type allow_anonymous: bool
    """

    from wikibaseintegrator.entities.baseentity import BaseEntity

    if isinstance(entities, str):
        entities = [entities]

    assert type(entities) == list

    params = {
        'action': 'wbgetentities',
        'ids': '|'.join(entities),
        'format': 'json'
    }

    reply = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)

    entity_instances = []
    for qid, v in reply['entities'].items():
        from wikibaseintegrator import WikibaseIntegrator
        wbi = WikibaseIntegrator()
        f = [x for x in BaseEntity.__subclasses__() if x.ETYPE == v['type']][0]
        ii = f(api=wbi).from_json(v)
        entity_instances.append((qid, ii))

    return entity_instances


def format_amount(amount) -> str:
    # Remove .0 by casting to int
    if float(amount) % 1 == 0:
        amount = int(float(amount))

    # Adding prefix + for positive number and 0
    if not str(amount).startswith('+') and float(amount) >= 0:
        amount = str('+{}'.format(amount))

    # return as string
    return str(amount)


def get_user_agent(user_agent, username=None):
    from wikibaseintegrator import __version__
    wbi_user_agent = "WikibaseIntegrator/{}".format(__version__)

    if user_agent is None:
        return_user_agent = wbi_user_agent
    else:
        return_user_agent = user_agent + ' ' + wbi_user_agent

    if username:
        return_user_agent += " (User:{})".format(username)

    return return_user_agent


def __deepcopy__(memo):
    # Don't return a copy of the module
    # Deepcopy don't allow copy of modules (https://bugs.python.org/issue43093)
    # It's really the good way to solve this?
    from wikibaseintegrator import wikibaseintegrator
    return wikibaseintegrator.wbi_helpers
