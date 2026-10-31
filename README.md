# Wikibase Integrator #

[![PyPi](https://img.shields.io/pypi/v/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![Python pytest](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-pytest.yaml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-pytest.yaml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/LeMyst/WikibaseIntegrator/badges/coverage.json)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-pytest.yaml)
[![Python Code Quality and Lint](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-lint.yaml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-lint.yaml)
[![CodeQL](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql.yml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql.yml)
[![Pyversions](https://img.shields.io/pypi/implementation/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![Documentation](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/docs.yaml/badge.svg)](https://lemyst.github.io/WikibaseIntegrator/)

WikibaseIntegrator is a Python library to read and write the data of a Wikibase instance, like
[Wikidata](https://www.wikidata.org/): items, properties, lexemes and MediaInfo entities, with their labels, claims,
qualifiers and references, through the MediaWiki API and the SPARQL endpoint. Its "fast run" mode compares your data
with the SPARQL endpoint and only writes what actually changed.

## Installation

```bash
python -m pip install wikibaseintegrator
```

Python 3.11 or newer is required.

## Quick example

```python
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config

# Wikimedia asks every tool to identify itself: https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
config['USER_AGENT'] = 'MyTool/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

wbi = WikibaseIntegrator()
item = wbi.item.get('Q582')
print(item.labels.get('en'))  # Villeurbanne
```

To log in and write, see [Login](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/login.html) and [Entities](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/entities.html).

## Documentation

The documentation is on **[GitHub Pages](https://lemyst.github.io/WikibaseIntegrator/)**, for the latest release and for the
development version:

- [Installation and configuration](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/installation.html): using another Wikibase instance, the User-Agent
  policy, debugging
- [Entities](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/entities.html): read, create and edit items, properties, lexemes, labels, claims, qualifiers
  and references
- [Login](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/login.html): OAuth 2.0, OAuth 1.0a, bot passwords
- [Data types](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/datatypes.html), [Structured Data on Commons](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/mediainfo.html)
- [Helpers](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/helpers.html): SPARQL queries, search, merges, the MediaWiki API, EditGroups
- [Fast run](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/fastrun.html) and [examples](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/examples.html), including a bot for mass import
- [API reference](https://lemyst.github.io/WikibaseIntegrator/en/latest/api/index.html)

Upgrading from v0.13 or v0.12? See the [breaking changes](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/upgrading.html).

## Contributing

See [Contributing](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/contributing.html) to set up the development environment and run the tests.

WikibaseIntegrator is a fork of [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator), see
[About](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/about.html). To port a WikidataIntegrator script, see
the [migration guide](https://lemyst.github.io/WikibaseIntegrator/en/latest/guide/wikidataintegrator.html).
