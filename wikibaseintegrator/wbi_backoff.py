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


def wbi_backoff_backoff_hdlr(details):
    exc_type, exc_value, _ = sys.exc_info()
    if exc_type == JSONDecodeError:
        logging.error(exc_value.doc)  # pragma: no cover
    logging.error("Backing off {wait:0.1f} seconds afters {tries} tries calling function with args {args} and kwargs {kwargs}".format(**details))  # pylint: disable=consider-using-f-string


def wbi_backoff_check_json_decode_error(e) -> bool:
    """
    Check if the error message is "Expecting value: line 1 column 1 (char 0)"
    if not, its a real error and we shouldn't retry
    """
    return isinstance(e, JSONDecodeError) and str(e) != "Expecting value: line 1 column 1 (char 0)"


wbi_backoff_exceptions = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.HTTPError, JSONDecodeError)

wbi_backoff = partial(backoff.on_exception, backoff.expo, wbi_backoff_exceptions, max_value=partial(config.get, 'BACKOFF_MAX_VALUE'), giveup=wbi_backoff_check_json_decode_error,
                      on_backoff=wbi_backoff_backoff_hdlr, jitter=None, max_tries=partial(config.get, 'BACKOFF_MAX_TRIES'))
