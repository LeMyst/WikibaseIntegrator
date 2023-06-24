#
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath('../..'))

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.mathjax',
              'sphinx.ext.viewcode',
              'sphinx_rtd_theme',
              'sphinx_github_changelog',
              'm2r2',
              'sphinx_autodoc_typehints']

# Provide a GitHub API token:
# Pass the SPHINX_GITHUB_CHANGELOG_TOKEN environment variable to your build
# OR
# sphinx_github_changelog_token = ""

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = {'.rst': 'restructuredtext'}

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'WikibaseIntegrator'
copyright = f'{datetime.now().year}, LeMyst'
author = 'LeMyst and WikibaseIntegrator contributors'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.12.5.dev0'
# The full version, including alpha/beta/rc tags.
release = '0.12.5.dev0'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

autodoc_typehints = 'both'
autodoc_default_options = {
    'special-members': '__init__',
    'members': True,
    'undoc-members': True,
    'inherited-members': True,
    'show-inheritance': True,
    'exclude-members': 'subclasses'
}

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

html_theme_options = {
    'style_external_links': False,
    # Toc options
    'collapse_navigation': False
}

html_context = {
    'display_github': True,
    'github_user': 'LeMyst',
    'github_repo': 'WikibaseIntegrator',
    'github_version': 'master',
    "conf_py_path": "/docs/"
}


def skip(app, what, name, obj, would_skip, options):
    if name == "__init__":
        return False
    if name == "sparql_query":
        return True
    return would_skip


def setup(app):
    app.connect("autodoc-skip-member", skip)
