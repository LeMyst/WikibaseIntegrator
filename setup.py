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
        "ujson ~= 4.3.0"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pylint",
            "pylint-exit",
            "mypy"
        ],
        "coverage": ["pytest-cov"],
    },
)
