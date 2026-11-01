import inspect

import pytest

from wikibaseintegrator import wbi_exceptions, wbi_login
from wikibaseintegrator.wbi_exceptions import EmptyValueError, LoginError, MissingExtensionError, MWApiError, UnknownDatatypeError, WikibaseIntegratorError

EXCEPTIONS = [obj for _, obj in inspect.getmembers(wbi_exceptions, inspect.isclass) if issubclass(obj, BaseException) and obj.__module__ == wbi_exceptions.__name__]


@pytest.mark.parametrize('exception', EXCEPTIONS, ids=lambda exception: exception.__name__)
def test_every_exception_has_the_common_base_class(exception):
    assert issubclass(exception, WikibaseIntegratorError)
    assert exception.__doc__


def test_the_value_errors_are_still_value_errors():
    assert issubclass(EmptyValueError, ValueError)
    assert issubclass(UnknownDatatypeError, ValueError)


def test_login_error_is_still_importable_from_wbi_login():
    assert wbi_login.LoginError is LoginError


def test_catch_any_wikibaseintegrator_error():
    with pytest.raises(WikibaseIntegratorError):
        raise MissingExtensionError({'code': 'no-such-entity'}, extension='WikibaseLexeme')
    with pytest.raises(WikibaseIntegratorError):
        raise LoginError('Login failed')
    # An API error is still an MWApiError
    with pytest.raises(MWApiError):
        raise MissingExtensionError({'code': 'no-such-entity'}, extension='WikibaseLexeme')
