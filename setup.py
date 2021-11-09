from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
# https://github.com/pallets/flask/blob/main/setup.py
setup(
    name="wikibaseintegrator",
    install_requires=[
        "backoff ~= 1.11.1",
        "mwoauth ~= 0.3.7",
        "oauthlib ~= 3.1.1",
        "requests ~= 2.26.0",
        "simplejson ~= 3.17.5"
    ],
    extras_require={
        "dev": ["pytest"],
        "coverage": ["pytest-cov"],
    },
)
