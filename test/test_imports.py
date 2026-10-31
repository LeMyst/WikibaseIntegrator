"""
Import footprint of the package: the data model (models, datatypes) doesn't need the HTTP and OAuth stack, only the
entities, the login and the helpers do. Each check runs in a fresh interpreter, the test session having already imported
everything.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import wikibaseintegrator

#: The runtime dependencies of the HTTP layer
HTTP_STACK = {'oauthlib', 'requests', 'requests_oauthlib', 'ujson'}

PACKAGE_ROOT = Path(wikibaseintegrator.__file__).parent.parent


def run(code: str) -> str:
    """Run the code in a fresh interpreter importing this checkout of the package, and return its output."""
    return subprocess.check_output([sys.executable, '-c', code], cwd=PACKAGE_ROOT, text=True)


def loaded_by(module: str) -> set[str]:
    """The top-level modules of the HTTP stack loaded by importing the module."""
    output = run(f'''
import json, sys
before = set(sys.modules)
import {module}
print(json.dumps(sorted({{name.partition('.')[0] for name in set(sys.modules) - before}})))
''')
    return set(json.loads(output)) & HTTP_STACK


@pytest.mark.parametrize('module', ['wikibaseintegrator', 'wikibaseintegrator.models', 'wikibaseintegrator.datatypes'])
def test_data_model_without_the_http_stack(module):
    # The package used to import WikibaseIntegrator (and so wbi_helpers and wbi_login) eagerly, and Quantity took
    # format_amount() from wbi_helpers: every import loaded requests and oauthlib
    assert loaded_by(module) == set()


def test_entities_load_the_http_stack():
    assert loaded_by('wikibaseintegrator.entities') >= {'requests', 'oauthlib'}


def test_lazy_attributes():
    output = run('''
import wikibaseintegrator
from wikibaseintegrator.wikibaseintegrator import WikibaseIntegrator
print(wikibaseintegrator.WikibaseIntegrator is WikibaseIntegrator)
# A submodule stays reachable as an attribute of the package, as when the package imported them all
print(wikibaseintegrator.wbi_helpers.format_amount is wikibaseintegrator.datatypes.quantity.format_amount)
print('WikibaseIntegrator' in dir(wikibaseintegrator))
print(wikibaseintegrator.wbi_manifest.MANIFEST_PATH == '/wikibase-manifest/v0/manifest')
''')

    assert output.split() == ['True', 'True', 'True', 'True']


def test_unknown_attribute():
    with pytest.raises(AttributeError, match='has no attribute'):
        getattr(wikibaseintegrator, 'no_such_attribute')
