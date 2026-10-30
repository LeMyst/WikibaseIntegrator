"""
Multiple functions or classes that can be used to interact with the Wikibase instance.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import threading
import uuid
import warnings
from dataclasses import dataclass, field
from time import sleep
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus, urlparse

import requests
import ujson
from requests import Session
from requests.auth import AuthBase

from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import (AnonymousEditNotAllowedError, EmptyValueError, MaxRetriesReachedException, MissingExtensionError, ModificationFailed, MWApiError,
                                               NonExistentEntityError, SaveFailed, SearchError)

if TYPE_CHECKING:
    from wikibaseintegrator.datatypes import BaseDataType
    from wikibaseintegrator.entities.baseentity import BaseEntity
    from wikibaseintegrator.models import Claim
    from wikibaseintegrator.wbi_login import _Login

log = logging.getLogger(__name__)

# Sessions used for requests made without a Login instance, one per thread since requests.Session isn't thread-safe.
_thread_local = threading.local()


def _get_default_session() -> Session:
    """
    Return the session used for requests made without a Login instance, created on first use in each thread.
    Connections are kept alive between calls in a same thread, but no state is shared across threads.
    """
    session = getattr(_thread_local, 'session', None)
    if session is None:
        session = _thread_local.session = requests.Session()
    return session


def __getattr__(name: str) -> Any:
    # Backward compatibility for the former module-level sessions
    if name in ('default_session', 'helpers_session'):
        warnings.warn(f"wbi_helpers.{name} is deprecated, the session is now per-thread and private.", DeprecationWarning, stacklevel=2)
        return _get_default_session()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class BColors:
    """
    Default colors for pretty outputs.

    .. deprecated::
        Kept for backward compatibility only. The library no longer emits ANSI color codes in its logs.
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



# MediaWiki error codes meaning the server no longer considers the current session authenticated
# (e.g. its session store evicted/expired the session, see #902). A CSRF token fetched right before the
# failing call can still look valid, since generate_edit_credentials() reads it off the very session
# cookies that are now rejected; recovering requires a full re-login instead.
SESSION_LOST_ERROR_CODES = {'assertuserfailed', 'assertbotfailed', 'notloggedin'}

# The entity types provided by the WikibaseLexeme extension, and the IDs of these entities (L1, L1-F1, L1-S1),
# optionally prefixed by a federated repository name.
LEXEME_ENTITY_TYPES = ('lexeme', 'form', 'sense')
LEXEME_ID_PATTERN = re.compile(r'^(?:[a-zA-Z]+:)?L[1-9][0-9]*(?:-[FS][1-9][0-9]*)?$')


def _creatable_entity_types(mediawiki_api_url: str, session: Session, timeout: Any) -> list[str]:
    """
    Return the entity types the Wikibase instance can create with wbeditentity, e.g. ['item', 'property'] on a
    Wikibase instance without extension, plus 'lexeme', 'form' and 'sense' with WikibaseLexeme.
    """
    # A single attempt without waiting: this check only improves an error message
    json_data = mediawiki_api_call('POST', mediawiki_api_url=mediawiki_api_url, session=session, max_retries=1, retry_after=0, timeout=timeout,
                                   data={'action': 'paraminfo', 'modules': 'wbeditentity'})
    return _paraminfo_values(json_data, module='wbeditentity', parameter='new')


def _paraminfo_values(json_data: dict[str, Any], module: str, parameter: str) -> list[str]:
    """
    Return the values accepted by a parameter of an API module, from a paraminfo response. The list is empty if the
    module doesn't exist on the instance or if the parameter doesn't take a list of values.
    """
    for module_info in json_data.get('paraminfo', {}).get('modules', []):
        if module_info.get('name') == module:
            for parameter_info in module_info.get('parameters', []):
                if parameter_info.get('name') == parameter and isinstance(parameter_info.get('type'), list):
                    return list(parameter_info['type'])
    return []


def _lexeme_support_missing(data: dict[str, Any], error: dict[str, Any], mediawiki_api_url: str, session: Session, timeout: Any) -> bool:
    """
    Check whether an API error comes from a Lexeme request sent to a Wikibase instance without lexeme support (#500).
    Such an instance doesn't know the Lexeme API actions, the lexeme entity types, nor the lexeme IDs.

    :param data: The parameters of the failed request
    :param error: The error returned by the API
    :return: True if the error is caused by the missing WikibaseLexeme extension
    """
    code = str(error.get('code', ''))
    info = str(error.get('info', ''))
    action = str(data.get('action', ''))

    # 'Unrecognized value for parameter "action": wbladdform.' or 'Unrecognized value for parameter "new": lexeme.'
    # The code is 'badvalue' since MediaWiki 1.35, 'unknown_<parameter>' before.
    if code == 'badvalue' or code.startswith('unknown_'):
        if action.startswith('wbl') and 'parameter "action"' in info:
            return True
        return data.get('new') in LEXEME_ENTITY_TYPES and 'parameter "new"' in info

    # A repository supporting lexemes reports a missing lexeme as 'missing' in the wbgetentities response, the
    # 'no-such-entity' error means the ID itself is unknown. Confirm with the entity types the instance can create.
    if code == 'no-such-entity' and action == 'wbgetentities' and LEXEME_ID_PATTERN.match(str(error.get('id', ''))):
        try:
            return 'lexeme' not in _creatable_entity_types(mediawiki_api_url=mediawiki_api_url, session=session, timeout=timeout)
        except (MWApiError, MaxRetriesReachedException, requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            log.debug("Unable to check the lexeme support of the Wikibase instance", exc_info=True)
            return False

    return False


def mediawiki_api_call(method: str, mediawiki_api_url: str | None = None, session: Session | None = None, login: _Login | None = None, max_retries: int = 100, retry_after: int = 60,
                       **kwargs: Any) -> dict:
    """
    A function to call the MediaWiki API.

    :param method: 'GET' or 'POST'
    :param mediawiki_api_url:
    :param session: If a session is passed, it will be used. Otherwise, the current thread's default session is used
    :param login: If provided and the API reports that the session is no longer authenticated (see
                  SESSION_LOST_ERROR_CODES), it is used to fully re-authenticate before retrying, once per call.
    :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to `max_retries` times
    :param retry_after: Number of seconds to wait before retrying request (see max_retries)
    :param kwargs: Any additional keyword arguments to pass to requests.request
    :return: The data returned by the API as a dictionary
    """

    mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])

    # TODO: Add support for 'multipart/form-data' when using POST (https://www.mediawiki.org/wiki/API:Edit#Large_edits)

    if 'data' in kwargs and kwargs['data']:
        kwargs['data'] = dict(kwargs['data'])
        if 'format' not in kwargs['data']:
            kwargs['data'].update({'format': 'json'})
        elif kwargs['data']['format'] != 'json':
            raise ValueError("'format' can only be 'json' when using mediawiki_api_call()")

    # Apply a default timeout to avoid an unresponsive server blocking the process indefinitely (user can override).
    if 'timeout' not in kwargs:
        kwargs['timeout'] = config['TIMEOUT']

    response = None
    session = session or _get_default_session()
    reauthenticated = False
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
                log.error("%s: rate limited. sleeping for %d seconds", datetime.datetime.now(datetime.UTC), sleep_sec)
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
                log.error("%s: maxlag. sleeping for %d seconds", datetime.datetime.now(datetime.UTC), sleep_sec)
                sleep(sleep_sec)
                continue

            # readonly
            if 'code' in json_data['error'] and json_data['error']['code'] == 'readonly':  # pragma: no cover
                log.error("The Wikibase instance is currently in readonly mode, waiting for %s seconds", retry_after)
                sleep(retry_after)
                continue

            # session no longer valid: re-authenticate and retry instead of failing outright (#902). Only once: the same
            # error right after a fresh login doesn't come from a lost session, e.g. assertbotfailed for an account
            # without the bot right, and is raised below instead of logging in again on every retry.
            if 'code' in json_data['error'] and json_data['error']['code'] in SESSION_LOST_ERROR_CODES and login is not None and not reauthenticated:
                log.warning("%s: session no longer valid (%s). Re-authenticating and retrying.", datetime.datetime.now(datetime.UTC), json_data['error']['code'])
                login.reauthenticate()
                reauthenticated = True
                if 'data' in kwargs and kwargs['data'] and 'token' in kwargs['data']:
                    kwargs['data']['token'] = login.get_edit_token()
                continue

            # Lexeme request on a Wikibase instance without the WikibaseLexeme extension
            if _lexeme_support_missing(data=kwargs.get('data') or {}, error=json_data['error'], mediawiki_api_url=mediawiki_api_url, session=session,
                                       timeout=kwargs['timeout']):
                raise MissingExtensionError(json_data['error'], extension='WikibaseLexeme', response=json_data)

            # non-existent error
            if 'code' in json_data['error'] and json_data['error']['code'] in ['no-such-entity', 'missingtitle']:
                raise NonExistentEntityError(json_data['error'], response=json_data)

            # duplicate error
            if 'code' in json_data['error'] and json_data['error']['code'] == 'modification-failed':  # pragma: no cover
                raise ModificationFailed(json_data['error'], response=json_data)

            # sitelink conflict
            if ('code' in json_data['error'] and json_data['error']['code'] == 'failed-save' and
                    any([message.get('name', '') == 'wikibase-validator-sitelink-conflict'
                         for message in json_data['error'].get('messages', [])])):
                raise SaveFailed(json_data['error'], response=json_data)

            # others case
            raise MWApiError(json_data['error'], response=json_data)

        # there is no error or waiting. break out of this loop and parse response
        break
    else:
        # the first time I've ever used "for - else!!"
        # else executes if the for loop completes normally. i.e. does not encounter a `break`
        # in this case, that means it tried this api call 10 times
        raise MaxRetriesReachedException(f'The number of retries ({max_retries}) have been reached.')

    return json_data


def mediawiki_api_call_helper(data: dict[str, Any], login: _Login | None = None, mediawiki_api_url: str | None = None, user_agent: str | None = None, allow_anonymous: bool = False,
                              max_retries: int = 100, retry_after: int = 60, maxlag: int = 5, is_bot: bool = False, **kwargs: Any) -> dict:
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
    data = dict(data) if data is not None else None

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
                raise AnonymousEditNotAllowedError("Anonymous edit are not allowed by default. "
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

    return mediawiki_api_call('POST', mediawiki_api_url=mediawiki_api_url, session=session, login=login, data=data, headers=headers, max_retries=max_retries, retry_after=retry_after, **kwargs)


@wbi_backoff()
def execute_sparql_query(query: str, prefix: str | None = None, endpoint: str | None = None, user_agent: str | None = None, max_retries: int | None = None, retry_after: int = 60,
                         auth: tuple[str, str] | AuthBase | None = None, headers: dict[str, str] | None = None) -> dict[str, dict]:
    """
    Static method which can be used to execute any SPARQL query

    Server errors (HTTP 5xx), throttling (HTTP 429) and connection errors are retried by wbi_backoff, up to config['BACKOFF_MAX_TRIES'] times.
    If the Query Service still fails after that, the last exception (e.g. requests.HTTPError) is raised.

    :param prefix: The URI prefixes required for an endpoint, default is the Wikidata specific prefixes
    :param query: The actual SPARQL query string
    :param endpoint: The URL string for the SPARQL endpoint. Default is the URL for the Wikidata SPARQL endpoint
    :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
    :param max_retries: Deprecated and ignored, use config['BACKOFF_MAX_TRIES'] instead.
    :param retry_after: The number of seconds to wait after a HTTP 429 (Too Many Requests) response without a Retry-After header.
    :param auth: Authentication for a protected SPARQL endpoint: a (username, password) tuple for HTTP Basic auth or any
                 requests.auth.AuthBase instance. Default is config['SPARQL_AUTH'].
    :param headers: Additional HTTP headers sent with the query (e.g. {'Authorization': 'Bearer <token>'}). They override the default ones.
    :return: The results of the query are returned in JSON format
    :raises requests.HTTPError: If the Query Service returns an HTTP error, after the retries for the transient ones are exhausted
    """

    if max_retries is not None:
        warnings.warn("The max_retries parameter of execute_sparql_query() is deprecated and ignored, retries are handled by config['BACKOFF_MAX_TRIES'].", DeprecationWarning,
                      stacklevel=3)

    sparql_endpoint_url = str(endpoint or config['SPARQL_ENDPOINT_URL'])
    auth = auth if auth is not None else config['SPARQL_AUTH']
    user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

    hostname = urlparse(sparql_endpoint_url).hostname
    if hostname is not None and hostname.endswith(('wikidata.org', 'wikipedia.org', 'wikimedia.org')) and user_agent is None:
        log.warning('WARNING: Please set an user agent if you interact with a Wikibase instance from the Wikimedia Foundation.')
        log.warning('More information in the README.md and https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy')

    if prefix:
        query = prefix + '\n' + query

    body = {
        'query': '#Tool: WikibaseIntegrator wbi_functions.execute_sparql_query\n' + query,
        'format': 'json'
    }

    # Send the query in the request body (application/x-www-form-urlencoded, set automatically by requests for data=).
    # The previous 'multipart/form-data' Content-Type was incorrect (no multipart body was ever sent) and could be
    # rejected by stricter endpoints. Using the body also avoids URL length limits with large queries.
    request_headers = {
        'Accept': 'application/sparql-results+json',
        'User-Agent': get_user_agent(user_agent)
    }
    if headers:
        request_headers.update(headers)

    log.debug("SPARQL query:\n%s", body['query'])

    # Connection errors, and the requests.HTTPError raised below for 5xx and 429 responses, are retried by wbi_backoff
    response = _get_default_session().post(sparql_endpoint_url, data=body, headers=request_headers, auth=auth, timeout=config['TIMEOUT'])
    if response.status_code == 429:
        # Honour the delay asked by the Query Service before wbi_backoff retries
        try:
            retry_after = int(response.headers.get('retry-after', retry_after))
        except ValueError:
            pass  # Retry-After given as an HTTP date, keep the default delay
        log.error("Too Many Requests (429). Sleeping for %d seconds.", retry_after)
        sleep(retry_after)
    response.raise_for_status()

    return response.json()


def _check_empty_values(data: Any) -> None:
    """
    Check that every snak of the data sent to the API has a value when its snak type states that it has one: a datatype
    created with None or an empty string as value has an empty datavalue, which the Wikibase instance rejects with a
    less explicit error (#496). The statements of the forms and senses of a lexeme are checked too.

    :param data: The JSON representation of an entity, a form or a sense
    :exception EmptyValueError: if at least one snak has no value
    """
    problems: list[str] = []

    def check_snak(snak: Any, description: str) -> None:
        if isinstance(snak, dict) and snak.get('snaktype', 'value') == 'value' and not snak.get('datavalue'):
            problems.append(description)

    def check_statements(entity: dict, owner: str) -> None:
        statements = entity.get('claims', entity.get('statements')) or []
        if isinstance(statements, dict):
            statements = [statement for property_statements in statements.values() for statement in property_statements]

        for statement in statements:
            # A statement being removed only needs its ID
            if not isinstance(statement, dict) or 'remove' in statement:
                continue

            mainsnak = statement.get('mainsnak') or {}
            property_number = mainsnak.get('property')
            check_snak(mainsnak, f'{owner}claim {property_number}')
            for snaks in (statement.get('qualifiers') or {}).values():
                for snak in snaks:
                    check_snak(snak, f"{owner}qualifier {snak.get('property')} of a {property_number} claim")
            for reference in statement.get('references') or []:
                for snaks in (reference.get('snaks') or {}).values():
                    for snak in snaks:
                        check_snak(snak, f"{owner}reference {snak.get('property')} of a {property_number} claim")

    if not isinstance(data, dict):
        return

    check_statements(data, owner='')
    for section, name in (('forms', 'form'), ('senses', 'sense')):
        for sub_entity in data.get(section) or []:
            if isinstance(sub_entity, dict):
                check_statements(sub_entity, owner=f"{name} {sub_entity.get('id', '(new)')}: ")

    if problems:
        raise EmptyValueError(f"Missing value for: {', '.join(problems)}. Set a value, or use the WikibaseSnakType.NO_VALUE or WikibaseSnakType.UNKNOWN_VALUE "
                              f"snak type to state that there is no value or an unknown value.")


def _encoded_size(value: Any) -> int:
    """
    The size of a value serialized like the 'data' parameter of a write: JSON, then form-encoded in the request body.
    Form-encoding works character by character, so the size of a JSON array is the sum of the sizes of its parts.
    """
    return len(quote_plus(ujson.dumps(value)))


def _split_entity_data(data: dict[str, Any], max_request_size: int) -> list[dict[str, Any]]:
    """
    Split the data of an entity whose form-encoded size is larger than max_request_size into several parts, each one
    under that size (#463): the first part holds everything but the statements and as many statements as fit, the next
    parts hold the remaining statements.

    :param data: The JSON representation of an entity
    :param max_request_size: The maximum form-encoded size of each part, in bytes
    :return: The parts of the data, the data itself if it is small enough
    :exception ValueError: if the data without its statements, or a single statement, is larger than max_request_size
    """
    if _encoded_size(data) <= max_request_size:
        return [data]

    key = 'claims' if 'claims' in data else 'statements'  # 'statements' for MediaInfo
    statements = data.get(key) or []
    if isinstance(statements, dict):
        statements = [statement for property_statements in statements.values() for statement in property_statements]

    first: dict[str, Any] = {name: value for name, value in data.items() if name != key}
    first[key] = []
    current = first
    current_size = _encoded_size(first)
    if current_size > max_request_size:
        raise ValueError(f"The data of the entity without its statements is larger than the maximum request size ({max_request_size} bytes), it can't be split")

    parts = [first]
    separator_size = len(quote_plus(','))
    for statement in statements:
        statement_size = _encoded_size(statement)
        added_size = statement_size + (separator_size if current[key] else 0)
        if current_size + added_size > max_request_size:
            # The statement doesn't fit: it starts a new part
            current = {key: []}
            current_size = _encoded_size(current)
            added_size = statement_size
            if current_size + added_size > max_request_size:
                property_number = statement.get('mainsnak', {}).get('property') if isinstance(statement, dict) else None
                raise ValueError(f"A statement of property {property_number} is larger than the maximum request size ({max_request_size} bytes) on its own")
            parts.append(current)

        current[key].append(statement)
        current_size += added_size

    return parts


def edit_entity(data: dict, id: str | None = None, type: str | None = None, baserevid: int | None = None, summary: str | None = None, clear: bool = False, is_bot: bool = False,
                tags: list[str] | None = None, site: str | None = None, title: str | None = None, max_request_size: int | None = None, **kwargs: Any) -> dict:
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
    :param max_request_size: Maximum form-encoded size of the data, in bytes. Larger data is written with several edits:
        the first one with everything but the statements and as many statements as fit, then the remaining statements.
        The edits are not atomic: if one fails, the previous ones are kept. Default config['MAX_REQUEST_SIZE'] (None,
        never split).
    :param kwargs: More arguments for Python requests
    :return: The answer from the Wikibase API, of the last edit when the data is split
    """
    _check_empty_values(data)

    if not id and not (site and title) and not type:
        raise ValueError("The 'type' parameter is mandatory when creating a new entity (no id, site or title given).")

    if max_request_size is None:
        max_request_size = config['MAX_REQUEST_SIZE']
    parts = _split_entity_data(data, max_request_size) if max_request_size else [data]
    if len(parts) > 1:
        log.info("The data is larger than the maximum request size (%d bytes), it is written with %d edits", max_request_size, len(parts))

    json_result: dict = {}
    for position, part in enumerate(parts):
        params = {
            'action': 'wbeditentity',
            'data': ujson.dumps(part),
            'format': 'json'
        }

        # The base revision only applies to the first edit, the next ones are based on the previous edit
        if baserevid and position == 0:
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
            params.update({'new': str(type)})

        # Only the first edit may clear the entity, the next ones add the remaining statements
        if clear and position == 0:
            params.update({'clear': ''})

        if is_bot:
            params.update({'bot': ''})

        try:
            json_result = mediawiki_api_call_helper(data=params, is_bot=is_bot, **kwargs)
        except Exception as exception:
            if position > 0:
                exception.add_note(f"The write was split in {len(parts)} edits to stay under the maximum request size ({max_request_size} bytes): only the first {position} "
                                   f"were saved, on the entity {id}. Write the entity again to send the remaining statements.")
            raise

        # The next edits update the entity, created by the first edit if it is a new one
        if position + 1 < len(parts):
            id = json_result['entity']['id']

    return json_result


def merge_items(from_id: str, to_id: str, login: _Login | None = None, ignore_conflicts: list[str] | None = None, is_bot: bool = False, tags: list[str] | None = None,
                **kwargs: Any) -> dict:
    """
    A static method to merge two items. Wikibase turns the emptied item into a redirect to the target item.

    :param from_id: The ID to merge from. This parameter is required.
    :param to_id: The ID to merge to. This parameter is required.
    :param login: A wbi_login.Login instance
    :param ignore_conflicts: List of elements of the item to ignore conflicts for. Can only contain values of "description", "sitelink" and "statement"
    :param is_bot: Mark this edit as bot.
    :param tags: Change tags to apply to the revision.
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

    if tags:
        params.update({'tags': '|'.join(tags)})

    return mediawiki_api_call_helper(data=params, login=login, is_bot=is_bot, **kwargs)


def merge_multiple_items(item_ids: list[str], login: _Login | None = None, ignore_conflicts: list[str] | None = None, is_bot: bool = False, tags: list[str] | None = None,
                         **kwargs: Any) -> str:
    """
    Merge several items into the one with the lowest numeric ID, one wbmergeitems call per merged item.
    Each merged item is turned into a redirect by Wikibase.

    If a merge fails, the exception is raised and the merges already done are kept.

    :param item_ids: The IDs of the items to merge (at least two distinct IDs).
    :param login: A wbi_login.Login instance
    :param ignore_conflicts: List of elements of the item to ignore conflicts for. Can only contain values of "description", "sitelink" and "statement"
    :param is_bot: Mark these edits as bot.
    :param tags: Change tags to apply to the revisions.
    :return: The ID of the item all the others were merged into.
    """

    ids = []
    for item_id in item_ids:
        if not re.fullmatch(r'Q\d+', item_id.upper()):
            raise ValueError(f"Invalid item ID: {item_id}")
        if item_id.upper() not in ids:
            ids.append(item_id.upper())

    if len(ids) < 2:
        raise ValueError("At least two distinct item IDs are required to merge.")

    ids.sort(key=lambda x: int(x[1:]))
    to_id = ids[0]

    for from_id in ids[1:]:
        merge_items(from_id=from_id, to_id=to_id, login=login, ignore_conflicts=ignore_conflicts, is_bot=is_bot, tags=tags, **kwargs)
        log.info(f"Merged {from_id} into {to_id}")

    return to_id


def create_redirect(from_id: str, to_id: str, login: _Login | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    A static method to turn an item into a redirect to another item, with the wbcreateredirect API.

    The source item must be empty, deleted or already a redirect (to change its target, e.g. to fix a double redirect).
    To combine two items which both have content, use merge_items(), which creates the redirect itself.
    Wikibase only supports redirects between items with this API, and it doesn't accept a summary or change tags.

    :param from_id: The ID of the item to turn into a redirect. This parameter is required.
    :param to_id: The ID of the item to redirect to. It must exist and not be a redirect itself. This parameter is required.
    :param login: A wbi_login.Login instance
    :param is_bot: Mark this edit as bot.
    :return: The API response, with the ID of the target item in the 'redirect' key.
    """

    params = {
        'action': 'wbcreateredirect',
        'from': from_id,
        'to': to_id,
        'format': 'json'
    }

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


def set_claim(claim: Claim, entity_id: str | None = None, index: int | None = None, baserevid: int | None = None, summary: str | None = None, tags: list[str] | None = None,
              ignore_duplicate_mainsnak: bool = False, login: _Login | None = None, is_bot: bool = False, **kwargs: Any) -> dict:
    """
    Create or replace a single statement, with its qualifiers and references, with the wbsetclaim API.

    Unlike a write of the whole entity, only this statement is sent: the entity doesn't need to be loaded first, and the edit doesn't conflict with the edits of the other
    statements. A claim with an ID replaces the statement with this ID. A claim without an ID is added to the entity given by entity_id, and the ID generated for it is set on
    the claim once the edit is saved.

    :param claim: The claim to write, e.g. a datatype instance like String(prop_nr='P31', value='foo'). It can't be marked as removed, use remove_claims() instead.
    :param entity_id: The ID of the entity of a new claim (without ID). Optional for a claim with an ID, which already contains the ID of its entity.
    :param index: The position to move the statement to in the list of statements of the entity.
    :param baserevid: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
    :param summary: Summary for the edit. Will be prepended by an automatically generated comment.
    :param tags: Change tags to apply to the revision.
    :param ignore_duplicate_mainsnak: Don't save the statement if the entity already has a statement with the same main snak. The API then answers with a warning instead of the
        saved statement.
    :param login: A wbi_login.Login instance
    :param is_bot: Mark this edit as bot.
    :param kwargs: More arguments for mediawiki_api_call_helper() and Python requests
    :return: The API response, with the saved statement in the 'claim' key.
    :exception ValueError: if the claim is marked as removed, if a new claim has no entity_id, or if the ID of the claim doesn't match entity_id
    :exception EmptyValueError: if a snak of the claim has no value
    """

    if claim.removed:
        raise ValueError("The claim is marked as removed, use remove_claims() to delete it.")

    if claim.id:
        claim_entity_id = claim.id.split('$', 1)[0]
        if entity_id and entity_id.upper() != claim_entity_id.upper():
            raise ValueError(f"The claim {claim.id} belongs to {claim_entity_id}, not to {entity_id}.")
        guid = claim.id
    elif entity_id:
        # The API requires a GUID, made of the ID of the entity and a UUID, like Wikibase generates them
        guid = f'{entity_id.upper()}${uuid.uuid4()}'
    else:
        raise ValueError("The claim has no ID, the entity_id parameter is required to add it to an entity.")

    data = claim.get_json()
    data['id'] = guid
    _check_empty_values({'claims': [data]})

    params = {
        'action': 'wbsetclaim',
        'claim': ujson.dumps(data),
        'format': 'json'
    }

    if index is not None:
        params.update({'index': str(index)})

    if baserevid:
        params.update({'baserevid': str(baserevid)})

    if summary:
        params.update({'summary': summary})

    if tags:
        params.update({'tags': '|'.join(tags)})

    if ignore_duplicate_mainsnak:
        params.update({'ignoreduplicatemainsnak': ''})

    if is_bot:
        params.update({'bot': ''})

    json_result = mediawiki_api_call_helper(data=params, login=login, is_bot=is_bot, **kwargs)

    if 'claim' in json_result:
        claim.id = json_result['claim']['id']

    return json_result


def check_constraints(entity_id: str | list[str] | None = None, claim_id: str | list[str] | None = None, status: list[str] | None = None, allow_anonymous: bool = True,
                      **kwargs: Any) -> dict:
    """
    Check the constraint violations of one or more entities or claims, using the target Wikibase instance's own constraint checker
    (the ``wbcheckconstraints`` API module provided by the `WikibaseQualityConstraints
    <https://www.mediawiki.org/wiki/Extension:WikibaseQualityConstraints>`_ extension).

    This relies entirely on the constraints configured on the Wikibase instance being queried (e.g. on Wikidata itself), rather than
    on a hardcoded or Wikidata-specific set of rules, so it works the same way against any Wikibase instance that has the extension
    installed. If the extension isn't installed, the underlying API call will fail with a :class:`~wikibaseintegrator.wbi_exceptions.MWApiError`.

    :param entity_id: One or more entity IDs (item, property, lexeme, etc.) whose claims should be checked.
    :param claim_id: One or more claim GUIDs to check, instead of checking whole entities.
    :param status: Only return results with one of these statuses, e.g. ``['violation']``. By default, the API returns every status.
    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default since this is a read-only action.
    :param kwargs: Extra parameters for mediawiki_api_call_helper()
    :return: The data returned by the API as a dictionary
    """
    if not entity_id and not claim_id:
        raise ValueError("You must provide either 'entity_id' or 'claim_id'.")

    params: dict[str, Any] = {
        'action': 'wbcheckconstraints',
        'format': 'json'
    }

    if entity_id:
        params.update({'id': '|'.join(entity_id) if isinstance(entity_id, list) else entity_id})

    if claim_id:
        params.update({'claimid': '|'.join(claim_id) if isinstance(claim_id, list) else claim_id})

    if status:
        params.update({'status': '|'.join(status)})

    return mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)


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
    :param max_results: The maximum number of search results returned. Default is 50. A single API call is limited to 50
                        results; higher values trigger additional paginated calls and the returned list is truncated to this length.
    :param dict_result: Return the results as a detailed dictionary instead of a list of IDs.
    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default.
    """

    language = str(language or config['DEFAULT_LANGUAGE'])

    params = {
        'action': 'wbsearchentities',
        'search': search_string,
        'language': language,
        'type': search_type,
        'limit': min(max_results, 50),
        'format': 'json'
    }

    if strict_language:
        params.update({'strictlanguage': ''})

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

        # Stop once there is no more page or we gathered enough results
        if 'search-continue' not in search_results or len(results) >= max_results:
            break

        cont_count = search_results['search-continue']

    # A page holds up to 50 results, so the last page can overshoot max_results: truncate to the requested length
    return results[:max_results]


def parse_value(values: str | list[str], datatype: str | None = None, prop_nr: str | None = None, options: dict[str, Any] | None = None, validate: bool = False,
                allow_anonymous: bool = True, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Parse values written as text (e.g. '3 March 1850', '1850s', '12±0.5') into data values, with the parsers of the Wikibase instance and the wbparsevalue API.

    A value which can't be parsed (or isn't valid, with validate) doesn't raise an exception: its result has an 'error' key, with the error in 'messages' (and the
    validation errors in 'validation-errors'), so that all the values can be checked at once.

    :param values: One value or a list of values to parse. They are sent in batches of 50, the limit of the API.
    :param datatype: The datatype of the values, e.g. 'time', 'quantity', 'globe-coordinate' or 'wikibase-item'. Use either datatype or prop_nr.
    :param prop_nr: A property whose datatype is used (and whose constraints are checked by validate), e.g. 'P569'. Use either datatype or prop_nr.
    :param options: Options for the parser, e.g. {'lang': 'fr'} to parse dates written in French, or {'precision': 9} for a time value.
    :param validate: Also validate the parsed values against the datatype, e.g. that a URL has a scheme. A valid value has a 'valid' key.
    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default.
    :param kwargs: Extra parameters for mediawiki_api_call_helper()
    :return: One result per value, in the same order: a dictionary with the 'raw' value, and the parsed 'value' and its 'type' (the datavalue of a snak), or an 'error'
    :exception ValueError: if neither or both of datatype and prop_nr are given
    """

    if bool(datatype) == bool(prop_nr):
        raise ValueError("Exactly one of the datatype and prop_nr parameters is required.")

    if isinstance(values, str):
        values = [values]

    results: list[dict[str, Any]] = []
    for start in range(0, len(values), 50):
        batch = values[start:start + 50]

        params: dict[str, Any] = {
            'action': 'wbparsevalue',
            # A value containing '|' needs the alternative multi-value separator of MediaWiki, U+001F
            'values': '\x1f' + '\x1f'.join(batch) if any('|' in value for value in batch) else '|'.join(batch),
            'format': 'json'
        }

        if datatype:
            params.update({'datatype': datatype})
        else:
            params.update({'property': prop_nr})

        if options:
            params.update({'options': ujson.dumps(options)})

        if validate:
            params.update({'validate': ''})

        try:
            json_result = mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)
        except MWApiError as error:
            # When a value can't be parsed, the API returns the error of the first one, along with the results of all the values
            if not error.response or 'results' not in error.response:
                raise
            json_result = error.response

        results.extend(json_result['results'])

    return results


def get_available_badges(allow_anonymous: bool = True, **kwargs: Any) -> list[str]:
    """
    Get the items which can be used as badges of sitelinks (e.g. 'Q17437796', featured article, on Wikidata), with the wbavailablebadges API.
    Each Wikibase instance configures its own list of badges, which can be empty. A sitelink with another item as badge can't be saved.

    :param allow_anonymous: Allow anonymous interaction with the MediaWiki API. 'True' by default.
    :param kwargs: Extra parameters for mediawiki_api_call_helper()
    :return: The IDs of the badge items
    """
    params = {
        'action': 'wbavailablebadges',
        'format': 'json'
    }

    return mediawiki_api_call_helper(data=params, allow_anonymous=allow_anonymous, **kwargs)['badges']


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

    _check_empty_values(data)

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

    _check_empty_values(data)

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

    _check_empty_values(data)

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

    _check_empty_values(data)

    params = {
        'action': 'wbleditsenseelements',
        'senseId': sense_id,
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
    Removes Sense from Lexeme

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
        # Use the recursive subclass registry (not __subclasses__(), which only returns direct subclasses) so that
        # entities inheriting through an intermediate base (Item/Property/MediaInfo via TermsEntity) are found.
        f = [x for x in BaseEntity.subclasses if x.ETYPE == v['type']][0]
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
    """
    Build a WikibaseIntegrator entity from a raw Wikibase JSON string.

    .. warning::
        **Experimental.** This function (and its helper :func:`_json2datatype`) is incomplete (references are not
        attached, several data types are unsupported, it relies on a mutable module-level cache and has no test
        coverage). Its API and behaviour may change or be removed without notice.
    """
    warnings.warn("format2wbi() is experimental and may change or be removed without notice.", stacklevel=2)

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

        from wikibaseintegrator.models.qualifiers import Qualifiers
        from wikibaseintegrator.models.references import References
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
    """
    Experimental helper for :func:`format2wbi`. See its docstring for caveats. May change or be removed without notice.
    """
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

    f = BaseDataType.get_datatype_class(datatype)
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

    response = _get_default_session().get(wikibase_url + '/entity/' + entity + '.ttl', headers=headers, timeout=config['TIMEOUT'])
    response.raise_for_status()
    results = response.text

    return results


@dataclass
class WikibaseCheck:
    """
    The features of a Wikibase instance, as returned by check_wikibase(). Print it for a readable report.
    """
    mediawiki_api_url: str
    mediawiki_version: str | None = None
    concept_base_uri: str | None = None
    extensions: list[str] = field(default_factory=list)  # The names of the installed MediaWiki extensions
    entity_types: list[str] = field(default_factory=list)  # The entity types the instance can create (item, property, lexeme...)
    datatypes: list[str] = field(default_factory=list)  # The property datatypes the instance supports
    sparql_endpoint_url: str | None = None
    sparql_available: bool | None = None  # None when the SPARQL endpoint wasn't checked
    problems: list[str] = field(default_factory=list)  # The problems found, empty when everything is fine

    @property
    def is_wikibase(self) -> bool:
        """The instance is a Wikibase repository: it can create entities."""
        return bool(self.entity_types)

    @property
    def has_lexemes(self) -> bool:
        """The instance supports lexemes (WikibaseLexeme). The extension can be installed without lexeme support."""
        return 'lexeme' in self.entity_types

    @property
    def has_mediainfo(self) -> bool:
        """The instance supports MediaInfo entities (WikibaseMediaInfo, Structured Data on Commons)."""
        return 'mediainfo' in self.entity_types

    @property
    def has_search(self) -> bool:
        """The instance has WikibaseCirrusSearch: the statements can be searched, e.g. with the haswbstatement keyword."""
        return 'WikibaseCirrusSearch' in self.extensions

    @property
    def has_quality_constraints(self) -> bool:
        """The instance has WikibaseQualityConstraints, needed by check_constraints()."""
        return 'WikibaseQualityConstraints' in self.extensions

    def __str__(self) -> str:
        def yes_no(value: bool) -> str:
            return 'yes' if value else 'no'

        sparql = 'not checked' if self.sparql_available is None else ('available' if self.sparql_available else 'not available')
        lines = [
            f'Wikibase instance: {self.mediawiki_api_url}',
            f'MediaWiki version: {self.mediawiki_version or "unknown"}',
            f'Concept base URI: {self.concept_base_uri or "unknown"}',
            f'Entity types: {", ".join(self.entity_types) or "none"}',
            f'Datatypes: {", ".join(self.datatypes) or "none"}',
            f'Lexemes: {yes_no(self.has_lexemes)}, MediaInfo: {yes_no(self.has_mediainfo)}, Search (WikibaseCirrusSearch): {yes_no(self.has_search)}, '
            f'Quality constraints: {yes_no(self.has_quality_constraints)}',
            f'SPARQL endpoint: {self.sparql_endpoint_url or "none"} ({sparql})',
        ]
        if self.problems:
            lines.append('Problems:')
            lines.extend(f'- {problem}' for problem in self.problems)
        else:
            lines.append('No problem found')
        return '\n'.join(lines)


def check_wikibase(mediawiki_api_url: str | None = None, sparql_endpoint_url: str | None = None, wikibase_url: str | None = None, check_sparql: bool = True,
                   login: _Login | None = None, **kwargs: Any) -> WikibaseCheck:
    """
    Check the features of a Wikibase instance: the MediaWiki version, the installed extensions, the entity types and the
    datatypes it supports, and whether the SPARQL endpoint answers. It also checks the configuration of
    WikibaseIntegrator: a 'WIKIBASE_URL' not matching the concept URIs of the instance breaks the SPARQL queries built
    by WikibaseIntegrator (fast run mode, ...). The problems found are listed in the 'problems' attribute.

    Example: print(check_wikibase())

    :param mediawiki_api_url: The URL to the MediaWiki API. Default config['MEDIAWIKI_API_URL'].
    :param sparql_endpoint_url: The URL to the SPARQL endpoint. Default config['SPARQL_ENDPOINT_URL'].
    :param wikibase_url: The Wikibase URL compared with the concept URIs of the instance. Default config['WIKIBASE_URL'].
    :param check_sparql: Send a test query to the SPARQL endpoint.
    :param login: A login instance, to check a private instance.
    :param kwargs: More arguments for mediawiki_api_call_helper()
    :return: A WikibaseCheck object
    """
    mediawiki_api_url = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
    wikibase_url = str(wikibase_url or config['WIKIBASE_URL'])
    result = WikibaseCheck(mediawiki_api_url=mediawiki_api_url)

    siteinfo = mediawiki_api_call_helper(data={'action': 'query', 'meta': 'siteinfo', 'siprop': 'general|extensions', 'format': 'json'}, mediawiki_api_url=mediawiki_api_url,
                                         login=login, allow_anonymous=True, **kwargs)['query']
    result.mediawiki_version = siteinfo['general'].get('generator')
    result.concept_base_uri = siteinfo['general'].get('wikibase-conceptbaseuri')
    result.extensions = sorted(extension['name'] for extension in siteinfo.get('extensions', []))

    # The entity types wbeditentity can create, and the datatypes wbformatvalue accepts
    paraminfo = mediawiki_api_call_helper(data={'action': 'paraminfo', 'modules': 'wbeditentity|wbformatvalue', 'format': 'json'}, mediawiki_api_url=mediawiki_api_url,
                                          login=login, allow_anonymous=True, **kwargs)
    result.entity_types = _paraminfo_values(paraminfo, module='wbeditentity', parameter='new')
    result.datatypes = _paraminfo_values(paraminfo, module='wbformatvalue', parameter='datatype')

    if not result.is_wikibase:
        result.problems.append('The MediaWiki instance is not a Wikibase repository: the wbeditentity API module is missing')

    if result.concept_base_uri and result.concept_base_uri.rstrip('/') != wikibase_url.rstrip('/') + '/entity':
        expected_wikibase_url = result.concept_base_uri.rstrip('/').removesuffix('/entity')
        result.problems.append(f"The Wikibase URL '{wikibase_url}' doesn't match the concept URIs of the instance ('{result.concept_base_uri}'), "
                               f"set config['WIKIBASE_URL'] to '{expected_wikibase_url}'")

    if check_sparql:
        result.sparql_endpoint_url = str(sparql_endpoint_url or config['SPARQL_ENDPOINT_URL'])
        user_agent = str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None
        try:
            # A single attempt, without the retries of execute_sparql_query(): an unavailable endpoint is reported
            response = _get_default_session().post(result.sparql_endpoint_url, data={'query': 'ASK {}', 'format': 'json'}, auth=config['SPARQL_AUTH'], timeout=config['TIMEOUT'],
                                                   headers={'Accept': 'application/sparql-results+json', 'User-Agent': get_user_agent(user_agent)})
            response.raise_for_status()
            response.json()
            result.sparql_available = True
        except (requests.RequestException, ValueError) as exception:
            result.sparql_available = False
            result.problems.append(f"The SPARQL endpoint '{result.sparql_endpoint_url}' is not available: {exception}")

    return result

# def __deepcopy__(memo):
#     # Don't return a copy of the module
#     # Deepcopy don't allow copy of modules (https://bugs.python.org/issue43093)
#     # It's really the good way to solve this?
#     from wikibaseintegrator import wikibaseintegrator
#     return wikibaseintegrator.wbi_helpers

