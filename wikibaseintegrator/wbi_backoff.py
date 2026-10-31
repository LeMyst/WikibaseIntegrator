"""
Retry of the calls to the SPARQL endpoint and of the logins on transient errors, with an exponential wait between the
tries. It replaces the backoff library, archived since 2024, of which WikibaseIntegrator only used this.

The number of tries and the maximum wait are read from config['BACKOFF_MAX_TRIES'] and config['BACKOFF_MAX_VALUE'] at
each retry, so they can be changed at run time.
"""
import functools
import logging
import sys
import threading
import time
from collections.abc import Callable
from json import JSONDecodeError
from typing import Any, ParamSpec, TypeVar

import requests

from wikibaseintegrator.wbi_config import config

log = logging.getLogger(__name__)

P = ParamSpec('P')
R = TypeVar('R')

# Set while a retried call runs in the thread, so that the retried calls it makes are not retried on their own
_retrying = threading.local()

# Keyword arguments that may hold credentials and must not be written to the logs
SENSITIVE_KWARGS = {'auth', 'headers', 'login'}

# The client errors (HTTP 4xx) worth retrying: the others (bad request, not found, unauthorized...) give the same answer
# on every try
RETRIED_CLIENT_ERRORS = {408, 429}  # Request Timeout, Too Many Requests


class RetryAfterError(requests.HTTPError):
    """
    An HTTP 429 (Too Many Requests) response. wbi_backoff waits for retry_after seconds, the delay asked by the server,
    before the next try, instead of its exponential delay.
    """

    def __init__(self, *args: Any, retry_after: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


def wbi_backoff_backoff_hdlr(details: dict[str, Any]) -> None:
    """
    Log a retry. Called while handling the exception, with the details of the retry: 'args' and 'kwargs' of the
    retried call, 'tries' made so far and 'wait' in seconds before the next one.
    """
    exc_value = sys.exc_info()[1]
    # requests.exceptions.JSONDecodeError subclasses json.JSONDecodeError, so both are caught.
    if isinstance(exc_value, JSONDecodeError):
        log.error(exc_value.doc)  # pragma: no cover
    # Never log credentials passed to the retried function
    kwargs = {k: ('***' if k in SENSITIVE_KWARGS and v is not None else v) for k, v in details['kwargs'].items()}
    log.error("Backing off %0.1f seconds after %s tries calling function with args %r and kwargs %r", details['wait'], details['tries'], details['args'], kwargs)


def wbi_backoff_check_json_decode_error(e: BaseException) -> bool:
    """
    Check if the error message is "Expecting value: line 1 column 1 (char 0)"
    if not, its a real error and we shouldn't retry
    """
    return isinstance(e, JSONDecodeError) and str(e) != "Expecting value: line 1 column 1 (char 0)"


def wbi_backoff_giveup(e: BaseException) -> bool:
    """
    Give up immediately on permanent errors: a real JSON decode error, or a client error (HTTP 4xx) other than
    RETRIED_CLIENT_ERRORS, like a malformed query (400) or an authentication failure (401/403), which retrying the
    same request cannot fix.
    """
    if isinstance(e, requests.HTTPError) and e.response is not None and 400 <= e.response.status_code < 500:
        return e.response.status_code not in RETRIED_CLIENT_ERRORS
    return wbi_backoff_check_json_decode_error(e)


def wbi_backoff_wait(tries: int, e: BaseException) -> float:
    """
    The number of seconds to wait after the given number of failed tries: 1, 2, 4, 8... or, after a RetryAfterError,
    the delay asked by the server. Both are capped by config['BACKOFF_MAX_VALUE'].
    """
    wait: float = e.retry_after if isinstance(e, RetryAfterError) else 2 ** (tries - 1)
    max_value = config.get('BACKOFF_MAX_VALUE')
    return wait if max_value is None else min(wait, max_value)


def wbi_get_backoff_max_tries() -> int | None:
    return config.get('BACKOFF_MAX_TRIES')


# ChunkedEncodingError: the connection was closed before the end of the response, e.g. when the SPARQL endpoint cuts
# a long result. It is not a ConnectionError.
wbi_backoff_exceptions = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.HTTPError, JSONDecodeError)


def wbi_backoff() -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator retrying the call on the transient errors: the wbi_backoff_exceptions for which wbi_backoff_giveup()
    is False. The call is tried up to config['BACKOFF_MAX_TRIES'] times (None for no limit), then the last exception
    is raised.

    A decorated function called by another one, e.g. the __init__() of _Login called by the __init__() of a login
    class, is not retried on its own: its error goes up to the outermost decorated call, which retries the whole
    operation. Otherwise the tries would multiply at each level (5 x 5 token requests for a login).
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def retried(*args: P.args, **kwargs: P.kwargs) -> R:
            if getattr(_retrying, 'active', False):
                return func(*args, **kwargs)

            _retrying.active = True
            try:
                tries = 0
                while True:
                    tries += 1
                    try:
                        return func(*args, **kwargs)
                    except wbi_backoff_exceptions as e:
                        max_tries = wbi_get_backoff_max_tries()
                        if wbi_backoff_giveup(e) or (max_tries is not None and tries >= max_tries):
                            raise

                        wait = wbi_backoff_wait(tries, e)
                        wbi_backoff_backoff_hdlr({'target': func, 'args': args, 'kwargs': kwargs, 'tries': tries, 'wait': wait})
                        time.sleep(wait)
            finally:
                _retrying.active = False

        return retried

    return decorator
