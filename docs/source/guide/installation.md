# Installation and configuration

## Installation

The easiest way to install WikibaseIntegrator is to use the `pip` package manager. WikibaseIntegrator supports Python
3.11 and above.

```bash
python -m pip install wikibaseintegrator
```

You can also clone the repository and install it, preferably in a virtualenv.

```bash
git clone https://github.com/LeMyst/WikibaseIntegrator.git

cd WikibaseIntegrator

python -m pip install --upgrade pip setuptools

python -m pip install .
```

If you want to install a specific branch or tag from the repository, you can use the following command:

```bash
python -m pip install git+https://github.com/LeMyst/WikibaseIntegrator.git@v0.14.0
```

where `v0.14.0` is the tag or branch you want to install.

You can also use Poetry:

```bash
python -m pip install --upgrade poetry

python -m poetry install
```

To check that the installation is correct, launch a Python console and run the following code (which will retrieve the
Wikidata element for [Human](https://www.wikidata.org/entity/Q5)):

```python
from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()
my_first_wikidata_item = wbi.item.get(entity_id='Q5')

# to check successful installation and retrieval of the data, you can print the json representation of the item
print(my_first_wikidata_item.get_json())
```

## Using a Wikibase instance

WikibaseIntegrator uses Wikidata as default endpoint. To use another instance of Wikibase instead, you can override the
wbi_config module.

An example for a Wikibase instance installed
with [wikibase-docker](https://github.com/wmde/wikibase-release-pipeline/tree/main/example), add this to the top of your
script:

```python
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['MEDIAWIKI_API_URL'] = 'http://localhost/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'http://localhost:8834/proxy/wdqs/bigdata/namespace/wdq/sparql'
wbi_config['WIKIBASE_URL'] = 'http://wikibase.svc'
```

You can find more default settings in the file wbi_config.py

### Request size limit

Some Wikibase instances (e.g. Wikibase.cloud) reject a request larger than a given size with an
`HTTP 413 Request Entity Too Large` error, for example when creating an entity with hundreds of statements. Set
`wbi_config['MAX_REQUEST_SIZE']` (in bytes, for every write) or pass `max_request_size` to `write()` to split such a
write into several edits: the first one with the labels, descriptions, aliases, sitelinks and as many statements as fit,
then the remaining statements. Keep a margin under the limit of the instance for the other parameters of the request.

```python
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['MAX_REQUEST_SIZE'] = 500_000  # bytes

item.write()  # written with several edits if needed
item.write(max_request_size=200_000)  # or for a single write
```

The edits are not atomic: if one of them fails, the previous ones are kept, and the error says how many were saved
on which entity. Writing the entity again sends the remaining statements. A single statement, or the data without its
statements, larger than the limit raises a `ValueError` before anything is written.

### Wikimedia Foundation User-Agent policy

If you interact with a Wikibase instance hosted by the Wikimedia Foundation (like Wikidata, Wikimedia Commons, etc.),
it's highly advised to follow the User-Agent policy that you can find on the
page [User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy)
of the Wikimedia Meta-Wiki.

You can set a complementary User-Agent by modifying the variable `wbi_config['USER_AGENT']` in wbi_config.

For example, with your library name and contact information:

```python
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'
```

## Debugging

You can enable debugging by adding this piece of code to the top of your project:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```
