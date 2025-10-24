"""
Multiple functions or classes that can be used to interact with the Wikibase instance.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
from time import sleep
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import requests
import ujson
from requests import Session

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import MaxRetriesReachedException, ModificationFailed, MWApiError, NonExistentEntityError, SaveFailed, SearchError

if TYPE_CHECKING:
    from wikibaseintegrator.datatypes import BaseDataType
    from wikibaseintegrator.entities.baseentity import BaseEntity
    from wikibaseintegrator.wbi_login import _Login

log = logging.getLogger(__name__)

helpers_session = requests.Session()


class BColors:
    """
    Default colors for pretty outputs.
    """
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


def mediawiki_api_call(method: str, mediawiki_api_url: str | None = None, session: Session | None = None, max_retries: int = 100, retry_after: int = 60, **kwargs: Any) -> dict:
    """
    A function to call the MediaWiki API.

    :param method: 'GET' or 'POST'
    :param mediawiki_api_url:
    :param session: If a session is passed, it will be used. Otherwise, a new requests session is created
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
            log.exception("Connection error: %s. Sleeping for %d seconds.", e, retry_after)
            sleep(retry_after)
            continue
        if response.status_code in (500, 502, 503, 504):
            log.error("Service unavailable (HTTP Code %d). Sleeping for %d seconds.", response.status_code, retry_after)
            sleep(retry_after)
            continue

        response.raise_for_status()
        json_data = response.json()
        # MediaWiki api response has code = 200 even if there are errors.
        # Rate limit doesn't return HTTP 429 either, may in the future.
        # https://phabricator.wikimedia.org/T172293
        if 'error' in json_data:
            # rate limiting
            if 'messages' in json_data['error'] and 'actionthrottledtext' in [message['name'] for message in json_data['error']['messages']]:  # pragma: no cover
                sleep_sec = int(response.headers.get('retry-after', retry_after))
                log.error("%s: rate limited. sleeping for %d seconds", datetime.datetime.now(datetime.timezone.utc), sleep_sec)
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
                log.error("%s: maxlag. sleeping for %d seconds", datetime.datetime.now(datetime.timezone.utc), sleep_sec)
                sleep(sleep_sec)
                continue

            # readonly
            if 'code' in json_data['error'] and json_data['error']['code'] == 'readonly':  # pragma: no cover
                log.error("The Wikibase instance is currently in readonly mode, waiting for %s seconds", retry_after)
                sleep(retry_after)
                continue

            # non-existent error
            if 'code' in json_data['error'] and json_data['error']['code'] in ['no-such-entity', 'missingtitle']:
                raise NonExistentEntityError(json_data['error'])

            # duplicate error
            if 'code' in json_data['error'] and json_data['error']['code'] == 'modification-failed':  # pragma: no cover
                raise ModificationFailed(json_data['error'])

            # sitelink conflict
            if ('code' in json_data['error'] and json_data['error']['code'] == 'failed-save' and
                    any([message.get('name', '') == 'wikibase-validator-sitelink-conflict'
                         for message in json_data['error'].get('messages', [])])):
                raise SaveFailed(json_data['error'])

            # others case
            raise MWApiError(json_data['error'])

        # there is no error or waiting. break out of this loop and parse response
        break
    else:
        # the first time I've ever used "for - else!!"
        # else executes if the for loop completes normally. i.e. does not encounter a `break`
        # in this case, that means it tried this api call 10 times
        raise MaxRetriesReachedException(f'The number of retries ({max_retries}) have been reached.')

    return json_data


def mediawiki_api_call_helper(data: dict[str, Any], login: _Login | None = None, mediawiki_api_url: str | None = None, user_agent: str | None = None, allow_anonymous: bool = False,
                              max_retries: int = 1000, retry_after: int = 60, maxlag: int = 5, is_bot: bool = False, **kwargs: Any) -> dict:
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
        log.warning('More information in the README.md and https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy')

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
def execute_sparql_query(query: str, prefix: str | None = None, endpoint: str | None = None, user_agent: str | None = None, max_retries: int = 1000, retry_after: int = 60) -> dict[
    str, dict]:
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
        log.warning('More information in the README.md and https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy')

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
            log.exception("Connection error: %s. Sleeping for %d seconds.", e, retry_after)
            sleep(retry_after)
            continue
        if response.status_code in (500, 502, 503, 504):
            log.error("Service unavailable (HTTP Code %d). Sleeping for %d seconds.", response.status_code, retry_after)
            sleep(retry_after)
            continue
        if response.status_code == 429:
            if 'retry-after' in response.headers.keys():
                retry_after = int(response.headers['retry-after'])
            log.error("Too Many Requests (429). Sleeping for %d seconds", retry_after)
            sleep(retry_after)
            continue
        response.raise_for_status()
        results = response.json()

        return results

    raise Exception(f"No result after {max_retries} retries.")


def edit_entity(data: dict, id: str | None = None, type: str | None = None, baserevid: int | None = None, summary: str | None = None, clear: bool = False, is_bot: bool = False,
                tags: list[str] | None = None, site: str | None = None, title: str | None = None, **kwargs: Any) -> dict:
    """
    Creates a single new Wikibase entity and modifies it with serialised information.

    :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
    :param id: The identifier for the entity, including the prefix. Use either id or site and title together.
    :param type: Set this to the type of the entity to be created. One of the following values: form, item, lexeme, property, sense
    :param baserevid: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
    :param summary: Summary for the edit. Will be prepended by an automatically generated comment.
    :param clear: If set, the complete entity is emptied before proceeding. The entity will not be saved before it is filled with the "data", possibly with parts excluded.
    :param is_bot: Mark this edit as bot.
    :param login: A login instance
    :param tags: Change tags to apply to the revision.
    :param site: An identifier for the site on which the page resides. Use together with title to make a complete sitelink.
    :param title: Title of the page to associate. Use together with site to make a complete sitelink.
    :param kwargs: More arguments for Python requests
    :return: The answer from the Wikibase API
    """
    params = {
        'action': 'wbeditentity',
        'data': ujson.dumps(data),
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': str(baserevid)})

    if summary:
        params.update({'summary': summary})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if id:
        params.update({'id': id})
    elif site and title:
        params.update({
            'site': site,
            'title': title
        })
    else:
        assert type
        params.update({'new': type})

    if clear:
        params.update({'clear': ''})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def merge_items(from_id: str, to_id: str, login: _Login | None = None, ignore_conflicts: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
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


def merge_lexemes(source: str, target: str, login: _Login | None = None, summary: str | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
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


def remove_claims(claim_id: str, summary: str | None = None, baserevid: int | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Delete a claim from an entity

    :param claim_id: One GUID or several (pipe-separated) GUIDs identifying the claims to be removed. All claims must belong to the same entity.
    :param summary: Summary for the edit. Will be prepended by an automatically generated comment.
    :param baserevid: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
    :param is_bot: Mark this edit as bot.
    """

    params: dict[str, str | int] = {
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


def search_entities(search_string: str, language: str | None = None, strict_language: bool = False, search_type: str = 'item', max_results: int = 50, dict_result: bool = False,
                    allow_anonymous: bool = True, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Performs a search for entities in the Wikibase instance using labels and aliases.
    You can have more information on the parameters in the MediaWiki API help (https://www.wikidata.org/w/api.php?action=help&modules=wbsearchentities)

    :param search_string: A string which should be searched for in the Wikibase instance (labels and aliases)
    :param language: The language in which to perform the search. This only affects how entities are selected. Default is 'en' from wbi_config.
                     You can see the list of languages for Wikidata at https://www.wikidata.org/wiki/Help:Wikimedia_language_codes/lists/all (Use the WMF code)
    :param strict_language: Whether to disable language fallback. Default is 'False'.
    :param search_type: Search for this type of entity. One of the following values: form, item, lexeme, property, sense, mediainfo
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


def lexeme_add_form(lexeme_id, data, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Adds Form to Lexeme

    :param lexeme_id: ID of the Lexeme, e.g. L10
    :param data: The serialized object that is used as the data source.
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    params = {
        'action': 'wbladdform',
        'lexemeId': lexeme_id,
        'data': ujson.dumps(data),
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def lexeme_edit_form(form_id: str, data, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Edits representations and grammatical features of a Form

    :param form_id: ID of the Form or the concept URI, e.g. L10-F2
    :param data: The serialized object that is used as the data source.
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    pattern = re.compile(r'^(?:.+\/entity\/)?(L[0-9]+-F[0-9]+)$')
    matches = pattern.match(form_id)

    if not matches:
        raise ValueError(f"Invalid Form ID ({form_id}), format must be 'L[0-9]+-F[0-9]+'")

    form_id = matches.group(1)

    params = {
        'action': 'wbleditformelements',
        'formId': form_id,
        'data': ujson.dumps(data),
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def lexeme_remove_form(form_id: str, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Removes Form from Lexeme

    :param form_id: ID of the Form or the concept URI, e.g. L10-F2
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    pattern = re.compile(r'^(?:.+\/entity\/)?(L[0-9]+-F[0-9]+)$')
    matches = pattern.match(form_id)

    if not matches:
        raise ValueError(f"Invalid Form ID ({form_id}), format must be 'L[0-9]+-F[0-9]+'")

    form_id = matches.group(1)

    params = {
        'action': 'wblremoveform',
        'id': form_id,
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def lexeme_add_sense(lexeme_id, data, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Adds a Sense to a Lexeme

    :param lexeme_id: ID of the Lexeme, e.g. L10
    :param data: JSON-encoded data for the Sense, i.e. its glosses
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    params = {
        'action': 'wbladdsense',
        'lexemeId': lexeme_id,
        'data': ujson.dumps(data),
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def lexeme_edit_sense(sense_id: str, data, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Edits glosses of a Sense

    :param sense_id: ID of the Sense or the concept URI, e.g. L10-S2
    :param data: The serialized object that is used as the data source.
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    pattern = re.compile(r'^(?:.+\/entity\/)?(L[0-9]+-S[0-9]+)$')
    matches = pattern.match(sense_id)

    if not matches:
        raise ValueError(f"Invalid Sense ID ({sense_id}), format must be 'L[0-9]+-S[0-9]+'")

    sense_id = matches.group(1)

    params = {
        'action': 'wbleditsenseelements',
        'formId': sense_id,
        'data': ujson.dumps(data),
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def lexeme_remove_sense(sense_id: str, baserevid: int | None = None, tags: list[str] | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Adds Form to Lexeme

    :param sense_id: ID of the Sense, e.g. L10-S20
    :param baserevid: Base Revision ID of the Lexeme, if edit conflict check is wanted.
    :param tags: Change tags to apply to the revision.
    :param is_bot: Mark this edit as bot.
    :param kwargs:
    :return:

    """

    pattern = re.compile(r'^(?:.+\/entity\/)?(L[0-9]+-S[0-9]+)$')
    matches = pattern.match(sense_id)

    if not matches:
        raise ValueError(f"Invalid Sense ID ({sense_id}), format must be 'L[0-9]+-S[0-9]+'")

    sense_id = matches.group(1)

    params = {
        'action': 'wblremovesense',
        'id': sense_id,
        'format': 'json'
    }

    if baserevid:
        params.update({'baserevid': baserevid})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if is_bot:
        params.update({'bot': ''})

    return mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)


def generate_entity_instances(entities: str | list[str], allow_anonymous: bool = True, **kwargs: Any) -> list[tuple[str, BaseEntity]]:
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
    from wikibaseintegrator import WikibaseIntegrator
    for qid, v in reply['entities'].items():
        wbi = WikibaseIntegrator(is_bot=kwargs.get('is_bot', False), login=kwargs.get('login', None))
        f = [x for x in BaseEntity.__subclasses__() if x.ETYPE == v['type']][0]
        ii = f(api=wbi).from_json(v)
        entity_instances.append((qid, ii))

    return entity_instances


def delete_page(title: str | None = None, pageid: int | None = None, reason: str | None = None, deletetalk: bool = False, watchlist: str = 'preferences',
                watchlistexpiry: str | None = None, login: _Login | None = None, **kwargs: Any) -> dict:
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

    params: dict[str, Any] = {
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


def fulltext_search(search: str, max_results: int = 50, allow_anonymous: bool = True, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Perform a fulltext search on the mediawiki instance.
    It's an exception to the "only wikibase related function" rule! WikibaseIntegrator is focused on wikibase-only functions to avoid spreading out and covering all functions of MediaWiki.

    :param search: Search for page titles or content matching this value. You can use the search string to invoke special search features, depending on what the wiki's search backend implements.
    :param max_results: How many total pages to return. The value must be between 1 and 500.
    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default.
    :param kwargs: Extra parameters for mediawiki_api_call_helper()
    :return:
    """
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': search,
        'srlimit': max_results,
        'format': 'json'
    }

    return mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)['query']['search']


def format_amount(amount: int | str | float) -> str:
    """
    A formatting function mostly used for Quantity datatype.
    :param amount: A int, float or str you want to pass to Quantity value.
    :return: A correctly formatted string amount by Wikibase standard.
    """
    # Remove .0 by casting to int
    if float(amount) % 1 == 0:
        amount = int(float(amount))

    # Adding prefix + for positive number and 0
    if not str(amount).startswith('+') and float(amount) >= 0:
        amount = str(f'+{amount}')

    # return as string
    return str(amount)


def get_user_agent(user_agent: str | None = None) -> str:
    """
    Return a user agent string suitable for interacting with the Wikibase instance.

    :param user_agent: An optional user-agent. If not provided, will generate a default user-agent.
    :return: A correctly formatted user agent.
    """
    from wikibaseintegrator import __version__
    wbi_user_agent = f"WikibaseIntegrator/{__version__}"

    if user_agent is None:
        return_user_agent = wbi_user_agent
    else:
        return_user_agent = user_agent + ' ' + wbi_user_agent

    return return_user_agent


properties_dt: dict = {}


def format2wbi(entitytype: str, json_raw: str, allow_anonymous: bool = True, wikibase_url: str | None = None, **kwargs) -> BaseEntity:
    wikibase_url = str(wikibase_url or config['WIKIBASE_URL'])
    json_decoded = json.loads(json_raw)
    # pprint(json_decoded)

    from wikibaseintegrator.entities.baseentity import BaseEntity

    entity_list = [x for x in BaseEntity.subclasses if x.ETYPE == entitytype]
    if not entity_list:
        raise ValueError(f'Unknown entity type: {entitytype}')

    entity = entity_list[0]()

    # Add aliases (for Item and MediaInfo)
    # Add lemmas (for Lexeme)
    # Add lexical_category (for Lexeme)
    # Add language (for Lexeme)
    # Add forms (for Lexeme)
    # Add senses (for Lexeme)
    # Add datatype (for Property)

    if 'descriptions' in json_decoded and hasattr(entity, 'descriptions'):
        for language in json_decoded['descriptions']:
            entity.descriptions.set(language=language, value=json_decoded['descriptions'][language])  # type: ignore

    if 'labels' in json_decoded and hasattr(entity, 'labels'):
        for language in json_decoded['labels']:
            entity.labels.set(language=language, value=json_decoded['labels'][language])  # type: ignore

    if 'claims' in json_decoded:
        properties = list(json_decoded['claims'].keys())

        from wikibaseintegrator.models import Qualifiers, References
        from wikibaseintegrator.wbi_enums import ActionIfExists

        params = {
            'action': 'wbgetentities',
            'ids': '|'.join(properties),
            'props': 'datatype',
            'format': 'json'
        }

        reply = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)

        for p in reply['entities']:
            properties_dt[p] = reply['entities'][p]['datatype']

        for claim in json_decoded['claims']:
            if isinstance(json_decoded['claims'][claim], list):
                statements = json_decoded['claims'][claim]
            else:
                statements = [json_decoded['claims'][claim]]

            for statement in statements:
                qualifiers = Qualifiers()
                if 'qualifiers' in statement:
                    if isinstance(statement['qualifiers'], list):
                        qualifiers_list = statement['qualifiers']
                    else:
                        qualifiers_list = [statement['qualifiers']]

                    for qualifiers_raw in qualifiers_list:
                        for qualifier in qualifiers_raw:
                            qualifiers.add(_json2datatype(qualifier, qualifiers_raw[qualifier], wikibase_url))

                references = References()
                if 'references' in statement:
                    if isinstance(statement['references'], list):
                        references_list = statement['references']
                    else:
                        references_list = [statement['references']]

                    for references_raw in references_list:
                        for reference in references_raw:
                            references.add(_json2datatype(reference, references_raw[reference], wikibase_url))
                # TODO: Add support for references
                sub_entity = _json2datatype(claim, statement, wikibase_url)
                sub_entity.qualifiers.set(qualifiers)
                # entity.references.set(references)
                entity.claims.add(sub_entity, action_if_exists=ActionIfExists.APPEND_OR_REPLACE)

    return entity


def _json2datatype(prop_nr: str, statement: dict, wikibase_url: str | None = None, allow_anonymous=True, **kwargs) -> BaseDataType:
    from wikibaseintegrator.datatypes.basedatatype import BaseDataType
    wikibase_url = str(wikibase_url or config['WIKIBASE_URL'])

    if prop_nr not in properties_dt:
        params = {
            'action': 'wbgetentities',
            'ids': prop_nr,
            'props': 'datatype',
            'format': 'json'
        }

        reply = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)

        for p in reply['entities']:
            properties_dt[p] = reply['entities'][p]['datatype']

    datatype = properties_dt[prop_nr]

    f = [x for x in BaseDataType.subclasses if x.DTYPE == datatype][0]
    if f.__name__ in ['CommonsMedia', 'ExternalID', 'Form', 'GeoShape', 'Item', 'Lexeme', 'Math', 'MusicalNotation', 'Property', 'Sense', 'String', 'TabularData', 'URL']:
        if isinstance(statement, dict):
            value = statement['value']
        else:
            value = statement
        return f(prop_nr=prop_nr, value=value)
    elif f.__name__ == 'GlobeCoordinate':
        altitude = statement['altitude'] or None
        precision = statement['precision'] or None
        globe = statement['globe'] or None
        return f(prop_nr=prop_nr, latitude=statement['latitude'], longitude=statement['longitude'], altitude=altitude, precision=precision, globe=globe, wikibase_url=wikibase_url)
    elif f.__name__ == 'MonolingualText':
        return f(prop_nr=prop_nr, language=statement['language'], text=statement['text'])
    elif f.__name__ == 'Quantity':
        upper_bound = statement['upper_bound'] or None
        lower_bound = statement['lower_bound'] or None
        unit = statement['unit'] or '1'
        return f(prop_nr=prop_nr, quantity=statement['quantity'], upper_bound=upper_bound, lower_bound=lower_bound, unit=unit, wikibase_url=wikibase_url)
    elif f.__name__ == 'Time':
        before = statement['before'] or 0
        after = statement['after'] or 0
        precision = statement['precision'] or None
        timezone = statement['timezone'] or 0
        calendarmodel = statement['calendarmodel'] or None
        return f(prop_nr=prop_nr, time=statement['time'], before=before, after=after, precision=precision, timezone=timezone, calendarmodel=calendarmodel,
                 wikibase_url=wikibase_url)

    return f()


def download_entity_ttl(entity: str, wikibase_url: str | None = None, user_agent: str | None = None) -> str:
    """
    Downloads the TTL (Terse RDF Triple Language) content of a specific entity from a Wikibase instance.

    Args:
    - entity (str): The identifier of the entity to download the TTL content for.
    - wikibase_url (str | None): The base URL of the Wikibase instance. If None, the default URL from the configuration
                                  will be used.
    - user_agent (str | None): The user agent string to be used in the HTTP request headers. If None, the default user
                                agent from the configuration will be used if available.

    Returns:
    - str: The TTL content of the requested entity.

    Raises:
    - HTTPError: If the HTTP request to retrieve the TTL content fails (status code other than 2xx).

    Note:
    The function relies on a configuration setup (presumably a 'config' dictionary) containing at least the keys
    'WIKIBASE_URL' and 'USER_AGENT' for the default Wikibase URL and user agent respectively.
    """
    wikibase_url = str(wikibase_url or config['WIKIBASE_URL'])
    user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

    headers = {
        'User-Agent': get_user_agent(user_agent)
    }

    response = helpers_session.get(wikibase_url + '/entity/' + entity + '.ttl', headers=headers)
    response.raise_for_status()
    results = response.text

    return results

# def __deepcopy__(memo):
#     # Don't return a copy of the module
#     # Deepcopy don't allow copy of modules (https://bugs.python.org/issue43093)
#     # It's really the good way to solve this?
#     from wikibaseintegrator import wikibaseintegrator
#     return wikibaseintegrator.wbi_helpers

