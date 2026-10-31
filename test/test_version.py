"""
The version of the package, from its metadata, or from the pyproject.toml of a checkout that isn't installed. Each
check runs in a fresh interpreter, to import the package again.
"""
import subprocess
import sys
import tomllib
from pathlib import Path

import wikibaseintegrator

PACKAGE_ROOT = Path(wikibaseintegrator.__file__).parent.parent

# Imported without metadata, like from a checkout that isn't installed
WITHOUT_METADATA = '''
import importlib.metadata

def version(name):
    raise importlib.metadata.PackageNotFoundError(name)

importlib.metadata.version = version
'''


def version_in_a_fresh_interpreter(setup: str = '') -> str:
    return subprocess.check_output([sys.executable, '-c', setup + '\nimport wikibaseintegrator\nprint(wikibaseintegrator.__version__)'], cwd=PACKAGE_ROOT, text=True).strip()


def test_version_from_the_metadata():
    assert wikibaseintegrator.__version__ == version_in_a_fresh_interpreter()


def test_version_of_a_checkout_without_metadata():
    # The import used to fail with a PackageNotFoundError
    with open(PACKAGE_ROOT / 'pyproject.toml', 'rb') as file:
        expected = tomllib.load(file)['tool']['poetry']['version']

    assert version_in_a_fresh_interpreter(WITHOUT_METADATA) == expected


def test_unknown_version(monkeypatch):
    # Without metadata nor a pyproject.toml next to the package (e.g. a copy of the package directory alone)
    import importlib.metadata  # pylint: disable=import-outside-toplevel

    def version(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, 'version', version)
    monkeypatch.setattr(wikibaseintegrator, '__file__', str(PACKAGE_ROOT / 'no-such-directory' / 'wikibaseintegrator' / '__init__.py'))

    assert wikibaseintegrator._version() == '0.0.0+unknown'
