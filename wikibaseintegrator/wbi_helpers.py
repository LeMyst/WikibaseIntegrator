from __future__ import annotations

import datetime
import logging
from time import sleep
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from requests import Session

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import MWApiError, NonExistentEntityError, SearchError

if TYPE_CHECKING:
    from wikibaseintegrator.entities.baseentity import BaseEntity
    from wikibaseintegrator.wbi_login import _Login

log = logging.getLogger(__name__)

helpers_session = requests.Session()


class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Session used for all anonymous requests
default_session = requests.Session()


def mediawiki_api_call(method: str, mediawiki_api_url: str = None, session: Session = None, max_retries: int = 100, retry_after: int = 60, **kwargs: Any) -> Dict:
    """
    A function to call the MediaWiki API.

    :param method: 'GET' or 'POST'
    :param mediawiki_api_url:
    :param session: If a session is passed, it will be used. Otherwise a new requests session is created
    :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to `max_retries` times
    :param retry_after: Number of seconds to wait before retrying request (see max_retries)
    :param kwargs: Any additional keyword arguments to pass to requests.request
    :return: The data returned by the API as a dictionary
    """

    mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])

    # TODO: Add support for 'multipart/form-data' when using POST (https://www.mediawiki.org/wiki/API:Edit#Large_edits)

    if 'data' in kwargs and kwargs['data']:
        if 'format' not in kwargs['data']:
            kwargs['data'].update({'format': 'json'})
        elif kwargs['data']['format'] != 'json':
            raise ValueError("'format' can only be 'json' when using mediawiki_api_call()")

    response = None
    session = session if session else default_session
    for n in range(max_retries):
        try:
            response = session.request(method=method, url=mediawiki_api_url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}. Sleeping for {retry_after} seconds.")
            sleep(retry_after)
            continue
        if response.status_code in (500, 502, 503, 504):
            logging.error(f"Service unavailable (HTTP Code {response.status_code}). Sleeping for {retry_after} seconds.")
            sleep(retry_after)
            continue

        response.raise_for_status()
        json_data = response.json()
        # MediaWiki api response has code = 200 even if there are errors.
        # Rate limit doesn't return HTTP 429 either, may in the future.
        # https://phabricator.wikimedia.org/T172293
        if 'error' in json_data:
            # rate limiting
            error_msg_names = set()
            if 'messages' in json_data['error']:
                error_msg_names = {x.get('name') for x in json_data['error']['messages']}
            if 'actionthrottledtext' in error_msg_names:  # pragma: no cover
                sleep_sec = int(response.headers.get('retry-after', retry_after))
                logging.error(f"{datetime.datetime.utcnow()}: rate limited. sleeping for {sleep_sec} seconds")
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
                logging.error(f"{datetime.datetime.utcnow()}: maxlag. sleeping for {sleep_sec} seconds")
                sleep(sleep_sec)
                continue

            # readonly
            if 'code' in json_data['error'] and json_data['error']['code'] == 'readonly':  # pragma: no cover
                logging.error(f'The Wikibase instance is currently in readonly mode, waiting for {retry_after} seconds')
                sleep(retry_after)
                continue

            # non-existent error
            if 'code' in json_data['error'] and json_data['error']['code'] in ['no-such-entity', 'missingtitle']:
                if 'info' in json_data['error']['code']:
                    raise NonExistentEntityError(json_data['error']['code']['info'])
                raise NonExistentEntityError()

            # others case
            raise MWApiError(response.json() if response else {})

        # there is no error or waiting. break out of this loop and parse response
        break
    else:
        # the first time I've ever used for - else!!
        # else executes if the for loop completes normally. i.e. does not encounter a `break`
        # in this case, that means it tried this api call 10 times
        raise MWApiError(response.json() if response else {})

    return json_data


def mediawiki_api_call_helper(data: Dict[str, Any], login: _Login = None, mediawiki_api_url: str = None, user_agent: str = None, allow_anonymous: bool = False,
                              max_retries: int = 1000, retry_after: int = 60, maxlag: int = 5, is_bot: bool = False, **kwargs: Any) -> Dict:
    """
    A simplified function to call the MediaWiki API.
    Pass the data, as a dictionary, related to the action you want to call, all commons options will be automatically managed.

    :param data: A dictionary containing the JSON data to send to the API
    :param login: A wbi_login._Login instance
    :param mediawiki_api_url: The URL to the MediaWiki API (default Wikidata)
    :param user_agent: The user agent (Recommended for Wikimedia Foundation instances)
    :param allow_anonymous: Allow an unidentified edit to the MediaWiki API (default False)
    :param max_retries: The maximum number of retries
    :param retry_after: The timeout between each retry
    :param maxlag: If applicable, the maximum lag allowed for the replication (An lower number reduce the load on the replicated database)
    :param is_bot: Flag the edit as a bot
    :param kwargs: Any additional keyword arguments to pass to requests.request
    :return: The data returned by the API as a dictionary
    """
    mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
    user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

    hostname = urlparse(mediawiki_api_url).hostname
    if hostname is not None and hostname.endswith(('wikidata.org', 'wikipedia.org', 'wikimedia.org')) and user_agent is None:
        log.warning('WARNING: Please set an user agent if you interact with a Wikibase instance from the Wikimedia Foundation.')
        log.warning('More information in the README.md and https://meta.wikimedia.org/wiki/User-Agent_policy')

    if not allow_anonymous:
        if login is None:
            # Force allow_anonymous as False by default to ask for a login object
            raise ValueError("allow_anonymous can't be False and login is None at the same time.")

        if mediawiki_api_url != login.mediawiki_api_url:
            raise ValueError("mediawiki_api_url can't be different with the one in the login object.")

    headers = {
        'User-Agent': get_user_agent(user_agent)
    }

    # Default token is anonymous
    if isinstance(data, dict) and 'token' not in data:
        data.update({'token': '+\\'})

    if data is not None:
        if not allow_anonymous:
            # Get edit token if there is a login instance
            if login is not None:
                data.update({'token': login.get_edit_token()})

            # Always assert user if allow_anonymous is False
            if 'assert' not in data:
                if is_bot:
                    data.update({'assert': 'bot'})
                else:
                    data.update({'assert': 'user'})

            if 'token' in data and data['token'] == '+\\':
                raise Exception("Anonymous edit are not allowed by default. "
                                "Set allow_anonymous to True to edit mediawiki anonymously or set the login parameter with a valid Login object.")
        else:
            if 'assert' not in data and login is None:
                # Assert anon if allow_anonymous is True and no Login instance
                data.update({'assert': 'anon'})

        if maxlag > 0:
            data.update({'maxlag': maxlag})

    if login is not None:
        session = login.get_session()
    else:
        session = None

    log.debug(data)

    return mediawiki_api_call('POST', mediawiki_api_url=mediawiki_api_url, session=session, data=data, headers=headers, max_retries=max_retries, retry_after=retry_after, **kwargs)


@wbi_backoff()
def execute_sparql_query(query: str, prefix: str = None, endpoint: str = None, user_agent: str = None, max_retries: int = 1000, retry_after: int = 60) -> Dict[str, Dict]:
    """
    Static method which can be used to execute any SPARQL query

    :param prefix: The URI prefixes required for an endpoint, default is the Wikidata specific prefixes
    :param query: The actual SPARQL query string
    :param endpoint: The URL string for the SPARQL endpoint. Default is the URL for the Wikidata SPARQL endpoint
    :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
    :param max_retries: The number time this function should retry in case of header reports.
    :param retry_after: the number of seconds should wait upon receiving either an error code or the Query Service is not reachable.
    :return: The results of the query are returned in JSON format
    """

    sparql_endpoint_url = str(endpoint or config['SPARQL_ENDPOINT_URL'])
    user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

    hostname = urlparse(sparql_endpoint_url).hostname
    if hostname is not None and hostname.endswith(('wikidata.org', 'wikipedia.org', 'wikimedia.org')) and user_agent is None:
        log.warning('WARNING: Please set an user agent if you interact with a Wikibase instance from the Wikimedia Foundation.')
        log.warning('More information in the README.md and https://meta.wikimedia.org/wiki/User-Agent_policy')

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

    log.debug("%s%s%s", BColors.WARNING, params['query'], BColors.ENDC)

    for _ in range(max_retries):
        try:
            response = helpers_session.post(sparql_endpoint_url, params=params, headers=headers)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}. Sleeping for {retry_after} seconds.")
            sleep(retry_after)
            continue
        if response.status_code in (500, 502, 503, 504):
            logging.error(f"Service unavailable (HTTP Code {response.status_code}). Sleeping for {retry_after} seconds.")
            sleep(retry_after)
            continue
        if response.status_code == 429:
            if 'retry-after' in response.headers.keys():
                retry_after = int(response.headers['retry-after'])
            logging.error(f"Too Many Requests (429). Sleeping for {retry_after} seconds")
            sleep(retry_after)
            continue
        response.raise_for_status()
        results = response.json()

        return results

    raise Exception(f"No result after {max_retries} retries.")


def merge_items(from_id: str, to_id: str, login: _Login = None, ignore_conflicts: List[str] = None, is_bot: bool = False, **kwargs: Any) -> Dict:
    """
    A static method to merge two items

    :param from_id: The ID to merge from. This parameter is required.
    :param to_id: The ID to merge to. This parameter is required.
    :param login: A wbi_login.Login instance
    :param ignore_conflicts: List of elements of the item to ignore conflicts for. Can only contain values of "description", "sitelink" and "statement"
    :param is_bot: Mark this edit as bot.
    """

    params = {
        'action': 'wbmergeitems',
        'fromid': from_id,
        'toid': to_id,
        'format': 'json'
    }

    if ignore_conflicts is not None:
        params.update({'ignoreconflicts': '|'.join(ignore_conflicts)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, login=login, is_bot=is_bot, **kwargs)


def merge_lexemes(source: str, target: str, login: _Login = None, summary: str = None, is_bot: bool = False, **kwargs: Any) -> Dict:
    """
    A static method to merge two lexemes

    :param source: The ID to merge from. This parameter is required.
    :param target: The ID to merge to. This parameter is required.
    :param login: A wbi_login.Login instance
    :param summary: Summary for the edit.
    :param is_bot: Mark this edit as bot.
    """

    params = {
        'action': 'wblmergelexemes',
        'fromid': source,
        'toid': target,
        'format': 'json'
    }

    if summary:
        params.update({'summary': summary})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, login=login, is_bot=is_bot, **kwargs)


def remove_claims(claim_id: str, summary: str = None, baserevid: int = None, is_bot: bool = False, **kwargs: Any) -> Dict:
    """
    Delete a claim from an entity

    :param claim_id: One GUID or several (pipe-separated) GUIDs identifying the claims to be removed. All claims must belong to the same entity.
    :param summary: Summary for the edit. Will be prepended by an automatically generated comment.
    :param baserevid: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
    :param is_bot: Mark this edit as bot.
    """

    params: Dict[str, Union[str, int]] = {
        'action': 'wbremoveclaims',
        'claim': claim_id,
        'format': 'json'
    }

    if summary:
        params.update({'summary': summary})

    if baserevid:
        params.update({'baserevid': baserevid})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def delete_page(title: str = None, pageid: int = None, reason: str = None, deletetalk: bool = False, watchlist: str = 'preferences', watchlistexpiry: str = None,
                login: _Login = None, **kwargs: Any) -> Dict:
    """
    Delete a page

    :param title: Title of the page to delete. Cannot be used together with pageid.
    :param pageid: Page ID of the page to delete. Cannot be used together with title.
    :param reason: Reason for the deletion. If not set, an automatically generated reason will be used.
    :param deletetalk: Delete the talk page, if it exists.
    :param watchlist: Unconditionally add or remove the page from the current user's watchlist, use preferences (ignored for bot users) or do not change watch.
                      One of the following values: nochange, preferences, unwatch, watch
    :param watchlistexpiry: Watchlist expiry timestamp. Omit this parameter entirely to leave the current expiry unchanged.
    :param login: A wbi_login.Login instance
    :param kwargs:
    :return:
    """

    if not title and not pageid:
        raise ValueError("A title or a pageid must be specified.")

    if title and pageid:
        raise ValueError("You can't specify a title and a pageid at the same time.")

    if pageid and not isinstance(pageid, int):
        raise ValueError("pageid must be an integer.")

    params: Dict[str, Any] = {
        'action': 'delete',
        'watchlist': watchlist,
        'format': 'json'
    }

    if title:
        params.update({'title': title})

    if pageid:
        params.update({'pageid': pageid})

    if reason:
        params.update({'reason': reason})

    if deletetalk:
        params.update({'deletetalk': ''})

    if watchlistexpiry:
        params.update({'watchlistexpiry': watchlistexpiry})

    return mediawiki_api_call_helper(data=params, login=login, **kwargs)


def search_entities(search_string: str, language: str = None, strict_language: bool = False, search_type: str = 'item', max_results: int = 50, dict_result: bool = False,
                    allow_anonymous: bool = True, **kwargs: Any) -> List[Dict[str, Any]]:
    """
    Performs a search for entities in the Wikibase instance using labels and aliases.
    You can have more information on the parameters in the MediaWiki API help (https://www.wikidata.org/w/api.php?action=help&modules=wbsearchentities)

    :param search_string: A string which should be searched for in the Wikibase instance (labels and aliases)
    :param language: The language in which to perform the search. This only affects how entities are selected. Default is 'en' from wbi_config.
                     You can see the list of languages for Wikidata at https://www.wikidata.org/wiki/Help:Wikimedia_language_codes/lists/all (Use the WMF code)
    :param strict_language: Whether to disable language fallback. Default is 'False'.
    :param search_type: Search for this type of entity. One of the following values: form, item, lexeme, property, sense
    :param max_results: The maximum number of search results returned. The value must be between 0 and 50. Default is 50
    :param dict_result: Return the results as a detailed dictionary instead of a list of IDs.
    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default.
    """

    language = str(language or config['DEFAULT_LANGUAGE'])

    params = {
        'action': 'wbsearchentities',
        'search': search_string,
        'language': language,
        'type': search_type,
        'limit': 50,
        'format': 'json'
    }

    if strict_language:
        params.update({'strict_language': ''})

    cont_count = 0
    results = []

    while True:
        params.update({'continue': cont_count})

        search_results = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)

        if search_results['success'] != 1:
            raise SearchError('Wikibase API wbsearchentities failed')

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

        cont_count = search_results['search-continue']

        if cont_count >= max_results:
            break

    return results


def generate_entity_instances(entities: Union[str, List[str]], allow_anonymous: bool = True, **kwargs: Any) -> List[Tuple[str, BaseEntity]]:
    """
    A method which allows for retrieval of a list of Wikidata entities. The method generates a list of tuples where the first value in the tuple is the entity's ID, whereas the
    second is the new instance of a subclass of BaseEntity containing all the data of the entity. This is most useful for mass retrieval of entities.

    :param entities: A list of IDs. Item, Property or Lexeme.
    :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
    :return: A list of tuples, first value in the tuple is the entity's ID, second value is the instance of a subclass of BaseEntity with the corresponding entity data.
    """

    from wikibaseintegrator.entities.baseentity import BaseEntity

    if isinstance(entities, str):
        entities = [entities]

    assert isinstance(entities, list)

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


def format_amount(amount: Union[int, str, float]) -> str:
    # Remove .0 by casting to int
    if float(amount) % 1 == 0:
        amount = int(float(amount))

    # Adding prefix + for positive number and 0
    if not str(amount).startswith('+') and float(amount) >= 0:
        amount = str(f'+{amount}')

    # return as string
    return str(amount)


def get_user_agent(user_agent: Optional[str]) -> str:
    from wikibaseintegrator import __version__
    wbi_user_agent = f"WikibaseIntegrator/{__version__}"

    if user_agent is None:
        return_user_agent = wbi_user_agent
    else:
        return_user_agent = user_agent + ' ' + wbi_user_agent

    return return_user_agent

# def __deepcopy__(memo):
#     # Don't return a copy of the module
#     # Deepcopy don't allow copy of modules (https://bugs.python.org/issue43093)
#     # It's really the good way to solve this?
#     from wikibaseintegrator import wikibaseintegrator
#     return wikibaseintegrator.wbi_helpers
