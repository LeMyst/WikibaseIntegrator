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


def wbi_backoff_backoff_hdlr(details):
    exc_type, exc_value, _ = sys.exc_info()
    if exc_type == JSONDecodeError:
        log.error(exc_value.doc)  # pragma: no cover
    log.error("Backing off %0.1f seconds afters %s tries calling function with args %r and kwargs %r", details['wait'], details['tries'], details['args'], details['kwargs'])


def wbi_backoff_check_json_decode_error(e) -> bool:
    """
    Check if the error message is "Expecting value: line 1 column 1 (char 0)"
    if not, its a real error and we shouldn't retry
    """
    return isinstance(e, JSONDecodeError) and str(e) != "Expecting value: line 1 column 1 (char 0)"


def wbi_get_backoff_max_tries():
    return config.get('BACKOFF_MAX_TRIES')


wbi_backoff_exceptions = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.HTTPError, JSONDecodeError)

wbi_backoff = partial(backoff.on_exception, backoff.expo, wbi_backoff_exceptions, max_value=partial(config.get, 'BACKOFF_MAX_VALUE'), giveup=wbi_backoff_check_json_decode_error,
                      on_backoff=wbi_backoff_backoff_hdlr, jitter=None, max_tries=wbi_get_backoff_max_tries)
