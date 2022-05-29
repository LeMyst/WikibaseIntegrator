# Wikibase Integrator #

[![PyPi](https://img.shields.io/pypi/v/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![Python package](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-package.yml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-package.yml)
[![CodeQL](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql-analysis.yml)
[![Pyversions](https://img.shields.io/pypi/implementation/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![Read the Docs](https://readthedocs.org/projects/pip/badge/?version=latest&style=flat)](https://wikibaseintegrator.readthedocs.io)

Wikibase Integrator is a python package whose purpose is to manipulate data present on a Wikibase instance (like
Wikidata).

# Breaking changes in v0.12 #

A complete rewrite of the WikibaseIntegrator core has been done in v0.12 which has led to some important changes.

It offers a new object-oriented approach, better code readability and support for Property, Lexeme and MediaInfo
entities (in addition to Item).

If you want to stay on v0.11.x, you can put this line in your requirements.txt:

```
wikibaseintegrator~=0.11.2
```

---

<!-- ToC generator: https://luciopaiva.com/markdown-toc/ -->

- [WikibaseIntegrator / WikidataIntegrator](#wikibaseintegrator--wikidataintegrator)
- [Documentation](#documentation)
- [Installation](#installation)
- [Using a Wikibase instance](#using-a-wikibase-instance)
    - [Wikimedia Foundation User-Agent policy](#wikimedia-foundation-user-agent-policy)
- [The Core Parts](#the-core-parts)
    - [Entity manipulation](#entity-manipulation)
    - [wbi_login](#wbi_login)
        - [Login using OAuth1 or OAuth2](#login-using-oauth1-or-oauth2)
            - [As a bot](#as-a-bot)
            - [To impersonate a user (OAuth 1.0a)](#to-impersonate-a-user-oauth-10a)
        - [Login with a bot password](#login-with-a-bot-password)
        - [Login with a username and a password](#login-with-a-username-and-a-password)
    - [Wikibase Data Types](#wikibase-data-types)
    - [Structured Data on Commons](#structured-data-on-commons)
        - [Retrieve data](#retrieve-data)
        - [Write data](#write-data)
- [Helper Methods](#helper-methods)
    - [Use MediaWiki API](#use-mediawiki-api)
    - [Execute SPARQL queries](#execute-sparql-queries)
    - [Wikibase search entities](#wikibase-search-entities)
    - [Merge Wikibase items](#merge-wikibase-items)
- [Examples (in "normal" mode)](#examples-in-normal-mode)
    - [Create a new Item](#create-a-new-item)
    - [Modify an existing item](#modify-an-existing-item)
    - [A bot for Mass Import](#a-bot-for-mass-import)
- [Examples (in "fast run" mode)](#examples-in-fast-run-mode)
- [Debugging](#debugging)

# WikibaseIntegrator / WikidataIntegrator #

WikibaseIntegrator (wbi) is a fork of [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) (wdi) whose
purpose is to focus on compatibility with Wikibase. There have been many improvements which have led to radical changes
in the code. See the [release notes](https://github.com/LeMyst/WikibaseIntegrator/releases) to find out what has
changed.

# Documentation #

A (basic) documentation generated from the python source code is available on
the [Read the Docs website](https://wikibaseintegrator.readthedocs.io/).

# Installation #

The easiest way to install WikibaseIntegrator is to use the `pip` package manager. WikibaseIntegrator supports Python
3.7 and above. If Python 2 is installed, `pip` will lead to an error indicating missing dependencies.

```bash
python -m pip install wikibaseintegrator
```

You can also clone the repo and run it with administrator rights or install it in a virtualenv.

```bash
git clone https://github.com/LeMyst/WikibaseIntegrator.git

cd WikibaseIntegrator

python -m pip install --upgrade pip setuptools

python -m pip install .
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

# Using a Wikibase instance #

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

## Wikimedia Foundation User-Agent policy ##

If you interact with a Wikibase instance hosted by the Wikimedia Foundation (like Wikidata, Wikimedia Commons, etc.),
it's highly advised to follow the User-Agent policy that you can find on the
page [User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy)
of the Wikimedia Meta-Wiki.

You can set a complementary User-Agent by modifying the variable `wbi_config['USER_AGENT']` in wbi_config.

For example, with your library name and contact information:

```python
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'
```

# The Core Parts #

WikibaseIntegrator supports two modes in which it can be used, a normal mode, updating each item at a time, and a fast
run mode, which preloads some data locally and then just updates items if the new data provided differs from Wikidata.
The latter mode allows for great speedups when tens of thousands of Wikidata elements need to be checked for updates,
but only a small number will eventually be updated, a situation typically encountered when synchronising Wikidata with
an external resource.

## Entity manipulation ##

WikibaseIntegrator supports the manipulation of Item, Property, Lexeme and MediaInfo entities through these classes:

* wikibaseintegrator.entities.item.Item
* wikibaseintegrator.entities.property.Property
* wikibaseintegrator.entities.lexeme.Lexeme
* wikibaseintegrator.entities.mediainfo.MediaInfo

Features:

* Loading a Wikibase entity based on its Wikibase entity ID.
* All Wikibase data types are implemented (and some data types implemented by extensions).
* Full access to the entire Wikibase entity in the form of a JSON dict representation.

## wbi_login ##

`wbi_login` provides the login functionality and also stores the cookies and edit tokens required (For security reasons,
every MediaWiki edit requires an edit token). There is multiple methods to login:

* `wbi_login.OAuth2(consumer_token, consumer_secret)` (recommended)
* `wbi_login.OAuth1(consumer_token, consumer_secret, access_token, access_secret)`
* `wbi_login.Clientlogin(user, password)`
* `wbi_login.Login(user, password)`

There is more parameters available. If you want to authenticate on another instance than Wikidata, you can set the
mediawiki_api_url, mediawiki_rest_url or mediawiki_index_url. Read the documentation for more information.

### Login using OAuth1 or OAuth2 ###

OAuth is the authentication method recommended by the MediaWiki developers. It can be used to authenticate a bot or to
use WBI as a backend for an application.

#### As a bot ####

If you want to use WBI with a bot account, you should use OAuth as
an [Owner-only consumer](https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers). This allows to use the
authentication without the "continue oauth" step.

The first step is to request a new OAuth consumer on your MediaWiki instance on the page
"Special:OAuthConsumerRegistration", the "Owner-only" (or "This consumer is for use only by ...") has to be checked and
the correct version of the OAuth protocol must be set (OAuth 2.0). You will get a consumer token and consumer secret
(and an access token and access secret if you chose OAuth 1.0a). For a Wikimedia instance (like Wikidata), you need to
use the [Meta-Wiki website](https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration).

Example if you use OAuth 2.0:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth2(consumer_token='<your_client_app_key>', consumer_secret='<your_client_app_secret>')
```

Example if you use OAuth 1.0a:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth1(consumer_token='<your_consumer_key>', consumer_secret='<your_consumer_secret>',
                                  access_token='<your_access_token>', access_secret='<your_access_secret>')
```

#### To impersonate a user (OAuth 1.0a) ####

If WBI is to be used as a backend for a web application, the script must use OAuth for authentication, WBI supports
this, you just need to specify consumer key and consumer secret when instantiating `wbi_login.Login`. Unlike login by
username and password, OAuth is a 2-step process, as manual confirmation of the user for the OAuth login is required.
This means that the `wbi_login.OAuth1.continue_oauth()` method must be called after creating the `wbi_login.Login`
instance.

Example:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth1(consumer_token='<your_consumer_key>', consumer_secret='<your_consumer_secret>')
login_instance.continue_oauth(oauth_callback_data='<the_callback_url_returned>')
```

The `wbi_login.OAuth1.continue_oauth()` method will either ask the user for a callback URL (normal bot execution) or
take a parameter. Thus, in the case where WBI is used as a backend for a web application for example, the callback will
provide the authentication information directly to the backend and thus no copy and paste of the callback URL is needed.

### Login with a bot password ###

It's a good practice to use [Bot password](https://www.mediawiki.org/wiki/Manual:Bot_passwords) instead of simple
username and password, this allows limiting the permissions given to the bot.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(user='<bot user name>', password='<bot password>')
```

### Login with a username and a password ###

If you want to log in with your user account, you can use the "clientlogin" authentication method. This method is not
recommended.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Clientlogin(user='<user name>', password='<password>')
```

## Wikibase Data Types ##

Currently, Wikibase supports 17 different data types. The data types are represented as their own classes in
wikibaseintegrator.datatypes. Each datatype has its own peculiarities, which means that some of them require special
parameters (e.g. Globe Coordinates). They are available under the namespace `wikibase.datatypes`.

The data types currently implemented:

* CommonsMedia
* ExternalID
* Form
* GeoShape
* GlobeCoordinate
* Item
* Lexeme
* Math
* MonolingualText
* MusicalNotation
* Property
* Quantity
* Sense
* String
* TabularData
* Time
* URL

Two additional data types are also implemented but require the installation of the MediaWiki extension to work properly:

* extra.EDTF ([Wikibase EDTF](https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF))
* extra.LocalMedia ([Wikibase Local Media](https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media))

For details of how to create values (=instances) with these data types, please (for now) consult the docstrings in the
source code or the documentation website. Of note, these data type instances hold the values and, if specified, data
type instances for references and qualifiers.

## Structured Data on Commons ##

WikibaseIntegrator supports SDC (Structured Data on Commons) to update a media file hosted on Wikimedia Commons.

### Retrieve data ###

```python
from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()
media = wbi.mediainfo.get('M16431477')

# Retrieve the first "depicts" (P180) claim
print(media.claims.get('P180')[0].mainsnak.datavalue['value']['id'])
```

### Write data ###

```python
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item

wbi = WikibaseIntegrator()
media = wbi.mediainfo.get('M16431477')

# Add the "depicts" (P180) claim
media.claims.add(Item(prop_nr='P180', value='Q3146211'))

media.write()
```

# Helper Methods #

## Use MediaWiki API ##

The method `wbi_helpers.mediawiki_api_call_helper()` allows you to execute MediaWiki API POST call. It takes a mandatory
data array (data) and multiple optionals parameters like a login object of type wbi_login.Login, a mediawiki_api_url
string if the MediaWiki is not Wikidata, a user_agent string to set a custom HTTP User Agent header, and an
allow_anonymous boolean to force authentication.

Example:

Retrieve last 10 revisions from Wikidata element Q2 (Earth):

```python
from wikibaseintegrator import wbi_helpers

data = {
    'action': 'query',
    'prop': 'revisions',
    'titles': 'Q2',
    'rvlimit': 10
}

print(wbi_helpers.mediawiki_api_call_helper(data=data, allow_anonymous=True))
```

## Execute SPARQL queries ##

The method `wbi_helpers.execute_sparql_query()` allows you to execute SPARQL queries without a hassle. It takes the
actual query string (query), optional prefixes (prefix) if you do not want to use the standard prefixes of Wikidata, the
actual endpoint URL (endpoint), and you can also specify a user agent for the http header sent to the SPARQL server (
user_agent). The latter is very useful to let the operators of the endpoint know who you are, especially if you execute
many queries on the endpoint. This allows the operators of the endpoint to contact you (e.g. specify an email address,
or the URL to your bot code repository.)

## Wikibase search entities ##

The method `wbi_helpers.search_entities()` allows for string search in a Wikibase instance. This means that labels,
descriptions and aliases can be searched for a string of interest. The method takes five arguments: The actual search
string (search_string), an optional server (mediawiki_api_url, in case the Wikibase instance used is not Wikidata), an
optional user_agent, an optional max_results (default 500), an optional language (default 'en'), and an option
dict_id_label to return a dict of item id and label as a result.

## Merge Wikibase items ##

Sometimes, Wikibase items need to be merged. An API call exists for that, and wbi_core implements a method accordingly.
`wbi_helpers.merge_items()` takes five arguments:

* the QID of the item which should be merged into another item (from_id)
* the QID of the item the first item should be merged into (to_id)
* a login object of type wbi_login.Login to provide the API call with the required authentication information
* a boolean if the changes need to be marked as made by a bot (is_bot)
* a flag for ignoring merge conflicts (ignore_conflicts), will do a partial merge for all statements which do not
  conflict. This should generally be avoided because it leaves a crippled item in Wikibase. Before a merge, any
  potential conflicts should be resolved first.

# Examples (in "normal" mode) #

In order to create a minimal bot based on wbi_core, two things are required:

* A datatype object containing a value.
* An entity object (Item/Property/Lexeme/...) which takes the data, does the checks and performs write.

An optional Login object can be used to be authenticated on the Wikibase instance.

## Create a new Item ##

```python
from wikibaseintegrator import wbi_login, WikibaseIntegrator
from wikibaseintegrator.datatypes import ExternalID
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login_instance)

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = ExternalID(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to
data = [entrez_gene_id]

# Create a new item
item = wbi.item.new()

# Set an english label
item.labels.set(language='en', value='Newly created item')

# Set a French description
item.descriptions.set(language='fr', value='Une description un peu longue')

item.claims.add(data)
item.write()
```

## Modify an existing item ##

```python
from wikibaseintegrator import wbi_login, WikibaseIntegrator
from wikibaseintegrator.datatypes import ExternalID
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login_instance)

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = ExternalID(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to
data = [entrez_gene_id]

# Search and then edit an Item
item = wbi.item.get(entity_id='Q141806')

# Set an english label but don't modify it if there is already an entry
item.labels.set(language='en', value='An updated item', action_if_exists=ActionIfExists.KEEP)

# Set a French description and replace the existing one
item.descriptions.set(language='fr', value='Une description un peu longue', action_if_exists=ActionIfExists.REPLACE)

item.claims.add(data)
item.write()
```

## A bot for Mass Import ##

An enhanced example of the previous bot just puts two of the three things into a 'for loop' and so allows mass creation,
or modification of items.

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Item, String, Time
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseDatePrecision

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
raw_data = {
    '50943': 'ENST00000376197',
    '1029': 'ENST00000498124'
}

wbi = WikibaseIntegrator(login=login_instance)

for entrez_id, ensembl in raw_data.items():
    # add some references
    references = [
        [
            Item(value='Q20641742', prop_nr='P248'),
            Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', precision=WikibaseDatePrecision.DAY),
            ExternalID(value='1017', prop_nr='P351')
        ]
    ]

    # data type object
    entrez_gene_id = String(value=entrez_id, prop_nr='P351', references=references)
    ensembl_transcript_id = String(value=ensembl, prop_nr='P704', references=references)

    # data goes into a list, because many data objects can be provided to
    data = [entrez_gene_id, ensembl_transcript_id]

    # Search for and then edit/create new item
    item = wbi.item.new()
    item.claims.add(data)
    item.write()
```

# Examples (in "fast run" mode) #

In order to use the fast run mode, you need to know the property/value combination which determines the data corpus you
would like to operate on. E.g. for operating on human genes, you need to know
that [P351](https://www.wikidata.org/entity/P351) is the NCBI Entrez Gene ID and you also need to know that you are
dealing with humans, best represented by the [found in taxon property (P703)](https://www.wikidata.org/entity/P703) with
the value [Q15978631](https://www.wikidata.org/entity/Q15978631) for Homo sapiens.

IMPORTANT: In order for the fast run mode to work, the data you provide in the constructor must contain at least one
unique value/id only present on one Wikidata element, e.g. an NCBI entrez gene ID, Uniprot ID, etc. Usually, these would
be the same unique core properties used for defining domains in wbi_core, e.g. for genes, proteins, drugs or your custom
domains.

Below, the normal mode run example from above, slightly modified, to meet the requirements for the fast run mode. To
enable it, ItemEngine requires two parameters, fast_run=True/False and fast_run_base_filter which is a dictionary
holding the properties to filter for as keys, and the item QIDs as dict values. If the value is not a QID but a literal,
just provide an empty string. For the above example, the dictionary looks like this:

```python
from wikibaseintegrator.datatypes import ExternalID, Item

fast_run_base_filter = [ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')]
```

The full example:

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Item, String, Time
from wikibaseintegrator.wbi_enums import WikibaseDatePrecision

# login object
login = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

fast_run_base_filter = [ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')]
fast_run = True

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
# You can iterate over any data source as long as you can map the values to Wikidata properties.
raw_data = {
    '50943': 'ENST00000376197',
    '1029': 'ENST00000498124'
}

for entrez_id, ensembl in raw_data.items():
    # add some references
    references = [
        [
            Item(value='Q20641742', prop_nr='P248')
        ],
        [
            Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', precision=WikibaseDatePrecision.DAY),
            ExternalID(value='1017', prop_nr='P351')
        ]
    ]

    # data type object
    entrez_gene_id = String(value=entrez_id, prop_nr='P351', references=references)
    ensembl_transcript_id = String(value=ensembl, prop_nr='P704', references=references)

    # data goes into a list, because many data objects can be provided to
    data = [entrez_gene_id, ensembl_transcript_id]

    # Search for and then edit/create new item
    wb_item = WikibaseIntegrator(login=login).item.new()
    wb_item.add_claims(claims=data)
    wb_item.init_fastrun(base_filter=fast_run_base_filter)
    wb_item.write()
```

Note: Fastrun mode checks for equality of property/value pairs, qualifiers (not including qualifier attributes), labels,
aliases and description, but it ignores references by default!
References can be checked in fast run mode by setting `use_refs` to `True`.

# Debugging #

You can enable debugging by adding this piece of code to the top of your project:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```
