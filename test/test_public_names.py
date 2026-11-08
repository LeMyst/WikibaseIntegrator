"""
The public names of the subpackages. The package ships type hints (py.typed): type checkers treat a name imported into a
module as private unless the module lists it in __all__ (Pyright reportPrivateImportUsage, mypy --strict), so the
__all__ of each subpackage must list every class it imports from its submodules.
"""
import importlib
import inspect

import pytest

import wikibaseintegrator
from wikibaseintegrator import wbi_exceptions, wbi_helpers, wbi_login
from wikibaseintegrator.datatypes.quantity import format_amount


@pytest.mark.parametrize('name', ['wikibaseintegrator.datatypes', 'wikibaseintegrator.datatypes.extra', 'wikibaseintegrator.entities', 'wikibaseintegrator.models'])
def test_all_lists_the_classes_of_the_subpackage(name):
    package = importlib.import_module(name)
    classes = {attribute for attribute, value in vars(package).items() if inspect.isclass(value) and value.__module__.startswith(f'{name}.')}

    assert classes
    assert sorted(package.__all__) == sorted(classes)
    assert len(package.__all__) == len(set(package.__all__))


def test_all_of_the_package():
    for name in wikibaseintegrator.__all__:
        assert getattr(wikibaseintegrator, name)


def test_compatibility_reexports():
    assert wbi_login.LoginError is wbi_exceptions.LoginError
    assert wbi_helpers.format_amount is format_amount
