"""
WikibaseIntegrator Library
~~~~~~~~~~~~~~~~~~~~~~~~~~

WikibaseIntegrator is a Wikibase library, written in Python, for human beings.
Basic read usage:

   >>> from wikibaseintegrator import WikibaseIntegrator
   >>> from wikibaseintegrator.wbi_config import config
   >>> config['USER_AGENT'] = 'Item Get Notebook'
   >>> wbi = WikibaseIntegrator()
   >>> q42 = wbi.item.get('Q42')
   >>> q42.labels.get('en').value
   'Douglas Adams'

Full documentation is available at <https://lemyst.github.io/WikibaseIntegrator/>.
"""

import importlib
import importlib.metadata
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .wikibaseintegrator import WikibaseIntegrator

__all__ = ['WikibaseIntegrator', '__version__']


def _version() -> str:
    """
    The version of the installed package. Imported from a checkout that isn't installed (e.g. through PYTHONPATH), the
    package has no metadata: the version is read from the pyproject.toml of the checkout, or unknown.
    """
    try:
        return importlib.metadata.version('wikibaseintegrator')
    except importlib.metadata.PackageNotFoundError:
        pass

    try:
        with open(Path(__file__).parent.parent / 'pyproject.toml', 'rb') as file:
            pyproject = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return '0.0.0+unknown'

    version = pyproject.get('project', {}).get('version') or pyproject.get('tool', {}).get('poetry', {}).get('version')
    return str(version) if version else '0.0.0+unknown'


__version__ = _version()

# The submodules, loaded on first access: importing the data model (wikibaseintegrator.models, .datatypes) doesn't load
# the HTTP and OAuth stack (requests, oauthlib), which only the entities, the login and the helpers need
_SUBMODULES = frozenset({'datatypes', 'entities', 'models', 'wbi_backoff', 'wbi_config', 'wbi_editgroups', 'wbi_enums', 'wbi_exceptions', 'wbi_fastrun', 'wbi_helpers',
                         'wbi_login', 'wbi_manifest', 'wikibaseintegrator'})


def __getattr__(name: str) -> Any:
    """Load WikibaseIntegrator, or a submodule used as an attribute of the package (PEP 562), when first accessed."""
    if name == 'WikibaseIntegrator':
        from .wikibaseintegrator import WikibaseIntegrator  # pylint: disable=import-outside-toplevel,redefined-outer-name
        return WikibaseIntegrator
    if name in _SUBMODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | {'WikibaseIntegrator'} | _SUBMODULES)
