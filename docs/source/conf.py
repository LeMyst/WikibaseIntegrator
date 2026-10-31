"""
Sphinx configuration of the WikibaseIntegrator documentation, published on GitHub Pages by .github/workflows/docs.yaml:
en/stable/ (the latest release) and en/latest/ (master).
"""
import os
import sys
from collections.abc import MutableMapping
from datetime import datetime

sys.path.insert(0, os.path.abspath('../..'))


def get_meta() -> MutableMapping:
    """Get project metadata from pyproject.toml file.

    Returns:
        MutableMapping
    """
    import tomllib

    toml_path = os.path.join(os.path.dirname(__file__), "../..", "pyproject.toml")

    with open(toml_path, "rb") as fopen:
        pyproject = tomllib.load(fopen)

    return pyproject


meta = get_meta()

SITE = 'https://lemyst.github.io/WikibaseIntegrator/'
# The published version of this build, set by the docs workflow: 'stable' (a release) or 'latest' (master)
DOCS_VERSION = os.environ.get('DOCS_VERSION', 'latest')

# -- General configuration ------------------------------------------------

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.autosummary',
              'sphinx.ext.intersphinx',
              'sphinx.ext.mathjax',
              'sphinx.ext.viewcode',
              'myst_parser',
              'sphinx_github_changelog',
              'sphinx_autodoc_typehints']

# The changelog page renders the GitHub release notes: pass a token with the SPHINX_GITHUB_CHANGELOG_TOKEN environment
# variable (the docs workflow does) to avoid the rate limit of anonymous requests.

templates_path = ['_templates']
source_suffix = {'.rst': 'restructuredtext', '.md': 'markdown'}

# The user guide (docs/source/guide/) is written in Markdown: anchors for the headings, so that a link like
# helpers.md#execute-sparql-queries works as on GitHub
myst_heading_anchors = 4
master_doc = 'index'

project = meta["tool"]["poetry"]["name"]
copyright = f'{datetime.now().year}, LeMyst'
author = ", ".join(meta["tool"]["poetry"]["authors"])
version = meta["tool"]["poetry"]["version"]
release = version

language = 'en'
exclude_patterns = []

# The canonical URL of the pages, on GitHub Pages: the documentation of the latest release
html_baseurl = f'{SITE}en/stable/'

# The builtin 'type' of the annotations (e.g. type[BaseDataType]) collides with the many 'type' attributes of the classes
suppress_warnings = ['ref.python']

# -- API reference ----------------------------------------------------------

# The topic pages of docs/source/api/ list the objects with autosummary, which generates one page per object
autosummary_generate = True
autosummary_imported_members = False

# A class page documents its own members: the members inherited from Claim are not repeated on every data type page.
# The entity and login classes, used through their inherited methods, use the class-inherited template instead.
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'exclude-members': 'subclasses, sparql_query',
}
autodoc_member_order = 'groupwise'
# The documentation of the class and of its __init__() are shown together, instead of a separate __init__ entry
autoclass_content = 'both'

# sphinx-autodoc-typehints: the types are shown in the parameter descriptions, not in the signatures
typehints_defaults = 'comma'
typehints_use_signature = False
typehints_use_signature_return = False

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None),
}

# -- Options for HTML output ----------------------------------------------

html_theme = 'pydata_sphinx_theme'
html_title = 'WikibaseIntegrator'
html_static_path = ['_static']

# Copied as they are to the root of the build: 404.html, the page GitHub Pages serves for a missing page (the docs workflow
# copies the one of en/latest/ to the root of the site), which redirects the old Read the Docs URLs
html_extra_path = ['_extra']
html_theme_options = {
    'github_url': 'https://github.com/LeMyst/WikibaseIntegrator',
    'icon_links': [{'name': 'PyPI', 'url': 'https://pypi.org/project/wikibaseintegrator/', 'icon': 'fa-brands fa-python'}],
    'navbar_end': ['version-switcher', 'theme-switcher', 'navbar-icon-links'],
    'switcher': {
        # The list of the versions, published with the development version
        'json_url': f'{SITE}en/latest/_static/switcher.json',
        'version_match': DOCS_VERSION,
    },
    # The switcher file of a new version is only online once it is published
    'check_switcher': False,
    # A banner on the development version, linking to the documentation of the latest release
    'show_version_warning_banner': True,
    'use_edit_page_button': True,
    'show_toc_level': 2,
    'navigation_with_keys': False,
}
html_context = {
    'github_user': 'LeMyst',
    'github_repo': 'WikibaseIntegrator',
    'github_version': 'master',
    'doc_path': 'docs/source',
}
