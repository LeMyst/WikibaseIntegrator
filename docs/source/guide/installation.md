# Installation and configuration

## Installation

The easiest way to install WikibaseIntegrator is to use the `pip` package manager. WikibaseIntegrator supports Python
3.11.5 and above.

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
python -m pip install git+https://github.com/LeMyst/WikibaseIntegrator.git@v0.14.3
```

where `v0.14.3` is the tag or branch you want to install.

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

### From the manifest of the instance

An instance with the [WikibaseManifest](https://www.mediawiki.org/wiki/Extension:WikibaseManifest) extension, like the
instances of [Wikibase.cloud](https://www.wikibase.cloud/), describes itself: its API endpoints, its query service and its
concept URIs. `wbi_manifest.get_manifest()` reads this description from the MediaWiki REST API of the instance, and
`apply()` sets the matching options of wbi_config (`MEDIAWIKI_API_URL`, `MEDIAWIKI_REST_URL`, `MEDIAWIKI_INDEX_URL`,
`WIKIBASE_URL` and `SPARQL_ENDPOINT_URL`):

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_manifest

manifest = wbi_manifest.get_manifest('https://wikibase.world/w/rest.php')
manifest.apply()

wbi = WikibaseIntegrator()
item = wbi.item.get('Q1')
```

The manifest also maps some Wikidata entities to their local ID, when the administrators configured it:
`manifest.local_id('P31')` gives the local property for "instance of" (P31 on Wikidata), or `None` without an
equivalent. `get_manifest()` raises a `MissingExtensionError` if the instance doesn't have the extension, which is the
case of Wikidata.

### Several instances in one process

wbi_config is shared by the whole process. To work with several instances at the same time, e.g. to copy data from
Wikidata to another Wikibase, give each `WikibaseIntegrator` its own configuration, with the keys of wbi_config. The
options it doesn't set are read from wbi_config, when they're used:

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login, wbi_manifest

wikidata = WikibaseIntegrator()  # wbi_config: Wikidata by default

login = wbi_login.Login(user='MyBot@MyBot', password='...', mediawiki_api_url='https://wikibase.world/w/api.php')
world = WikibaseIntegrator(login=login, config=wbi_manifest.get_manifest('https://wikibase.world/w/rest.php').config())
# Or by hand:
# world = WikibaseIntegrator(login=login, config={'MEDIAWIKI_API_URL': 'https://wikibase.world/w/api.php',
#                                                 'SPARQL_ENDPOINT_URL': 'https://wikibase.world/query/sparql',
#                                                 'WIKIBASE_URL': 'https://wikibase.world'})

label = wikidata.item.get('Q42').labels.get('en').value
item = world.item.new()
item.labels.set(language='en', value=label)
item.write()
```

The entities of an instance (`wbi.item`, `wbi.property`, `wbi.lexeme`, `wbi.mediainfo`) use its `MEDIAWIKI_API_URL`,
`USER_AGENT` and `MAX_REQUEST_SIZE` for their requests, its `WIKIBASE_URL` for `get_entity_url()`, its
`DEFAULT_LEXEME_LANGUAGE` for the new lexemes, and its `SPARQL_ENDPOINT_URL` and `WIKIBASE_URL` for the fast run mode
(`write_required()`). The arguments given to a method, like `mediawiki_api_url`, take precedence. `wbi.config` gives the
configuration of the instance, read-only.

A `Quantity`, a `Time` or a `GlobeCoordinate` built with a bare ID as unit, calendar model or globe (e.g.
`unit='Q11573'`) keeps it, and it is completed with the `WIKIBASE_URL` of the instance when the entity holding the value
is serialized, e.g. written. Out of an entity, as with `claim.get_json()`, `wbi_config['WIKIBASE_URL']` is used. Pass
`wikibase_url` to the data type to build the IRI at once.

The rest still reads wbi_config: the functions of `wbi_helpers` (pass them `mediawiki_api_url`, `wikibase_url`... as
before), the retries and the timeouts, and the default language of the labels. A login has its own URLs, given when it
is created, and its MediaWiki API URL must be the one of the instance.

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
