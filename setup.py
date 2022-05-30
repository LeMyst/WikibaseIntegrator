from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
# https://github.com/pallets/flask/blob/main/setup.py
setup(
    name="wikibaseintegrator",
    install_requires=[
        "backoff ~= 2.0.1",
        "mwoauth ~= 0.3.7",
        "oauthlib ~= 3.2.0",
        "requests ~= 2.27.1",
        "requests-oauthlib ~= 1.3.1",
        "ujson ~= 5.2.0"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pylint",
            "pylint-exit",
            "mypy",
            "codespell",
            "flynt"
        ],
        "docs": [
            "Sphinx ~= 4.5.0",
            "readthedocs-sphinx-ext ~= 2.1.5",
            "sphinx-rtd-theme ~= 1.0.0",
            "sphinx_github_changelog ~= 1.2.0",
            "m2r2 ~= 0.3.2",
            "sphinx-autodoc-typehints ~= 1.18.1"
        ],
        "notebooks": ["jupyter"],
        "coverage": ["pytest-cov"],
    },
)
