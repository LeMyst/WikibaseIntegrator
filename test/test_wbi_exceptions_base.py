import inspect

import pytest

from wikibaseintegrator import wbi_exceptions, wbi_login
from wikibaseintegrator.wbi_exceptions import EmptyValueError, LoginError, MissingExtensionError, MWApiError, NonExistentEntityError, UnknownDatatypeError, WikibaseIntegratorError

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


def test_missing_entity_exception_is_a_deprecated_name_of_non_existent_entity_error():
    # Merged in 0.15, removed in 1.0 (#453)
    with pytest.warns(DeprecationWarning, match='MissingEntityException is deprecated'):
        from wikibaseintegrator.wbi_exceptions import MissingEntityException  # pylint: disable=import-outside-toplevel,no-name-in-module
    assert MissingEntityException is NonExistentEntityError

    # The code catching it still catches the deleted entities
    with pytest.warns(DeprecationWarning), pytest.raises(wbi_exceptions.MissingEntityException):
        raise NonExistentEntityError({'code': 'missing', 'info': 'The entity Q1 is missing'})


def test_unknown_attribute_of_wbi_exceptions():
    with pytest.raises(AttributeError, match="has no attribute 'NoSuchError'"):
        getattr(wbi_exceptions, 'NoSuchError')


def test_catch_any_wikibaseintegrator_error():
    with pytest.raises(WikibaseIntegratorError):
        raise MissingExtensionError({'code': 'no-such-entity'}, extension='WikibaseLexeme')
    with pytest.raises(WikibaseIntegratorError):
        raise LoginError('Login failed')
    # An API error is still an MWApiError
    with pytest.raises(MWApiError):
        raise MissingExtensionError({'code': 'no-such-entity'}, extension='WikibaseLexeme')
