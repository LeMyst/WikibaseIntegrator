"""
WikibaseIntegrator implementation of backoff python library.
"""
import logging
import sys
from functools import partial
from json import JSONDecodeError

import backoff
import requests

from wikibaseintegrator.wbi_config import config

log = logging.getLogger(__name__)

# Keyword arguments that may hold credentials and must not be written to the logs
SENSITIVE_KWARGS = {'auth', 'headers', 'login'}


def wbi_backoff_backoff_hdlr(details):
    exc_type, exc_value, _ = sys.exc_info()
    # requests.exceptions.JSONDecodeError subclasses json.JSONDecodeError, so use issubclass to catch both.
    if exc_type is not None and issubclass(exc_type, JSONDecodeError):
        log.error(exc_value.doc)  # pragma: no cover
    # Never log credentials passed to the retried function
    kwargs = {k: ('***' if k in SENSITIVE_KWARGS and v is not None else v) for k, v in details['kwargs'].items()}
    log.error("Backing off %0.1f seconds afters %s tries calling function with args %r and kwargs %r", details['wait'], details['tries'], details['args'], kwargs)


def wbi_backoff_check_json_decode_error(e) -> bool:
    """
    Check if the error message is "Expecting value: line 1 column 1 (char 0)"
    if not, its a real error and we shouldn't retry
    """
    return isinstance(e, JSONDecodeError) and str(e) != "Expecting value: line 1 column 1 (char 0)"


def wbi_backoff_giveup(e) -> bool:
    """
    Give up immediately on permanent errors: a real JSON decode error, or an authentication/authorization
    failure (HTTP 401/403), which retrying with the same credentials cannot fix.
    """
    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code in (401, 403):
        return True
    return wbi_backoff_check_json_decode_error(e)


def wbi_get_backoff_max_tries():
    return config.get('BACKOFF_MAX_TRIES')


wbi_backoff_exceptions = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.HTTPError, JSONDecodeError)

wbi_backoff = partial(backoff.on_exception, backoff.expo, wbi_backoff_exceptions, max_value=partial(config.get, 'BACKOFF_MAX_VALUE'), giveup=wbi_backoff_giveup,
                      on_backoff=wbi_backoff_backoff_hdlr, jitter=None, max_tries=wbi_get_backoff_max_tries)
