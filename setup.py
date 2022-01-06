from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
# https://github.com/pallets/flask/blob/main/setup.py
setup(
    name="wikibaseintegrator",
    install_requires=[
        "backoff ~= 1.11.1",
        "mwoauth ~= 0.3.7",
        "oauthlib ~= 3.1.1",
        "requests >= 2.26,< 2.28",
        "ujson ~= 5.1.0"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pylint",
            "pylint-exit",
            "mypy"
        ],
        "docs": [
            "Sphinx ~= 4.2.0",
            "readthedocs-sphinx-ext ~= 2.1.4",
            "sphinx-rtd-theme ~= 1.0.0",
            "sphinx_github_changelog @ git+https://github.com/LeMyst/sphinx-github-changelog.git@1.0.8-Sphinx-4.2.0#egg=sphinx_github_changelog",
            "m2r2 ~= 0.3.1",
            "sphinx-autodoc-typehints ~= 1.12.0"
        ],
        "coverage": ["pytest-cov"],
    },
)
