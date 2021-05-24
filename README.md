# Wikibase Integrator #

[![Python package](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-package.yml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/python-package.yml)
[![CodeQL](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/LeMyst/WikibaseIntegrator/actions/workflows/codeql-analysis.yml)
[![Pyversions](https://img.shields.io/pypi/pyversions/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![PyPi](https://img.shields.io/pypi/v/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)

<!-- ToC generator: https://luciopaiva.com/markdown-toc/ -->

- [WikibaseIntegrator / WikidataIntegrator](#wikibaseintegrator--wikidataintegrator)
- [Installation](#installation)
- [Using a Wikibase instance](#using-a-wikibase-instance)
- [The Core Parts](#the-core-parts)
    - [wbi_item.Item](#wbi_coreitemengine)
    - [wbi_functions](#wbi_functions)
        - [Use MediaWiki API](#use-mediawiki-api)
    - [wbi_login.Login](#wbi_loginlogin)
        - [Login using OAuth1 or OAuth2](#login-using-oauth1-or-oauth2)
        - [Login with a username and a password](#login-with-a-username-and-a-password)
    - [Wikibase Data Types](#wikibase-data-types)
- [Helper Methods](#helper-methods)
    - [Execute SPARQL queries](#execute-sparql-queries)
    - [Use Mediawiki API](#use-mediawiki-api)
    - [Wikibase search entities](#wikibase-search-entities)
    - [Merge Wikibase items](#merge-wikibase-items)
- [Examples (in "normal" mode)](#examples-in-normal-mode)
    - [A Minimal Bot](#a-minimal-bot)
    - [A Minimal Bot for Mass Import](#a-minimal-bot-for-mass-import)
- [Examples (in "fast run" mode)](#examples-in-fast-run-mode)

# WikibaseIntegrator / WikidataIntegrator #

WikibaseIntegrator (wbi) is a fork from [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) (wdi) whose
purpose is to be focused on Wikibase compatibility. There have been many improvements that have led to breaking changes
in the code. Refer to the [release notes](https://github.com/LeMyst/WikibaseIntegrator/releases) to find out what has
changed.

# Installation #

The easiest way to install WikibaseIntegrator is using `pip`. WikibaseIntegrator supports Python 3.7 and higher. If
Python 2 is installed `pip` will lead to an error indicating missing dependencies.

```bash
pip install wikibaseintegrator
```

You can also clone the repo and execute with administrator rights or install into a virtualenv.

```bash
git clone https://github.com/LeMyst/WikibaseIntegrator.git

cd WikibaseIntegrator

python -m pip install pip setuptools

python setup.py install
```

To test for correct installation, start a Python console and execute the following (Will retrieve the Wikidata item
for ['Human'](https://www.wikidata.org/entity/Q5)):

```python

from wikibaseintegrator.entities import item

my_first_wikidata_item = item.Item(item_id='Q5')

# to check successful installation and retrieval of the data, you can print the json representation of the item
print(my_first_wikidata_item.get_json_representation())
```

# Using a Wikibase instance #

WikibaseIntegrator use Wikidata as default endpoint. To use a Wikibase instance instead, you can overload the
wbi_config.

An example for a Wikibase instance installed with [wikibase-docker](https://github.com/wmde/wikibase-docker), add this
to the top of your script:

```python
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['MEDIAWIKI_API_URL'] = 'http://localhost:8181/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'http://localhost:8989/bigdata/sparql'
wbi_config['WIKIBASE_URL'] = 'http://wikibase.svc'
```

You can find more default parameters in the file wbi_config.py

# The Core Parts #

wbi_core supports two modes it can be operated in, a normal mode, updating each item at a time and, a fast run mode,
which is pre-loading data locally and then just updating items if the new data provided is differing from what is in
Wikidata. The latter mode allows for great speedups (measured up to 9x) when tens of thousand of Wikidata items need to
be checked if they require updates but only a small number will finally be updated, a situation usually encountered when
keeping Wikidata in sync with an external resource.

wbi_core consists of a central class called ItemEngine and Login for authenticating with a MediaWiki isntance (like
Wikidata).

## wbi_item.Item ##

This is the central class which does all the heavy lifting.

Features:

* Load a Wikibase item based on data to be written (e.g. a unique central identifier)
* Load a Wikibase item based on its Wikibase item id (aka QID)
* Checks for conflicts automatically (e.g. multiple items carrying a unique central identifier will trigger an
  exception)
* Checks automatically if the correct item has been loaded by comparing it to the data provided
* All Wikibase data types implemented
* A dedicated wbi_item.Item.write() method allows loading and consistency checks of data before any write to Wikibase is
  performed
* Full access to the whole Wikibase item as a JSON document

There are two ways of working with Wikibase items:

* A user can provide data, and ItemEngine will search for and load/modify an existing item or create a new one, solely
  based on the data provided (preferred). This also performs consistency checks based on a set of SPARQL queries.
* A user can work with a selected QID to specifically modify the data on the item. This requires that the user knows
  what he/she is doing and should only be used with great care, as this does not perform consistency checks.

## wbi_functions ##

wbi_functions provides a set of static functions to request or manipulate data from MediaWiki API or SPARQL Service.

Features:

* Minimize the number of HTTP requests for reads and writes to improve performance
* Method to easily execute [SPARQL](https://query.wikidata.org) queries on the Wikibase SPARQL endpoint.

### Use MediaWiki API ###

WikibaseIntegrator don't have functions to make API call to non-wikibase actions. You can
use `wbi_functions.mediawiki_api_call_helper()` to make a custom call.

Example to get the last two revisions of entity Q42 :

```python
from wikibaseintegrator import wbi_functions

data = {
    'action': 'query',
    'prop': 'revisions',
    'titles': 'Q42',
    'rvlimit': 2,
    'rvprop': 'ids|timestamp|comment|user',
    'rvslots': 'main'
}

print(wbi_functions.mediawiki_api_call_helper(data, allow_anonymous=True))
```

## wbi_login.Login ##

### Login using OAuth1 or OAuth2 ###

OAuth is the authentication method recommended by the Mediawiki developpers. It can be used for authenticating a bot or
to use WBI as a backend for an application.

#### As a bot ####

If you want to use WBI with a bot account, you should use OAuth as
an [Owner-only consumer](https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers). This allows to use the
authentication without the "continue oauth" step.

The first step is to request a new OAuth consumer on your Mediawiki instance on the page "Special:
OAuthConsumerRegistration", the "Owner-only" (or "This consumer is for use only by ...") has to be checked. You will get
a consumer key, consumer secret, access token and access secret.

Example if you use OAuth 1.0a:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(consumer_key='<your_consumer_key>', consumer_secret='<your_consumer_secret>',
                                 access_token='<your_access_token>', access_secret='<your_access_secret>')
```

Example if you use OAuth 2.0:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(client_id='<your_client_app_key>', client_secret='<your_client_app_secret>')
```

#### To impersonate a user (OAuth 1.0a) ####

If WBI should be used as a backend for a webapp, the script should use OAuth for authentication, WBI supports this, you
just need to specify consumer key and consumer secret when instantiating `wbi_login.Login`. In contrast to username and
password login, OAuth is a 2 steps process as manual user confirmation for OAuth login is required. This means that the
method `wbi_login.Login.continue_oauth()` needs to be called after creating the `wbi_login.Login` instance.

Example:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(consumer_key='<your_consumer_key>', consumer_secret='<your_consumer_secret>')
login_instance.continue_oauth()
```

The method `wbi_login.Login.continue_oauth()` will either prompt the user for a callback URL (normal bot runs), or it
will take a parameter so in the case of WBI being used as a backend for e.g. a web app, where the callback will provide
the authentication information directly to the backend and so no copy and paste of the callback URL is required.

### Login with a username and a password ###

`wbi_login.Login` provides the login functionality and also stores the cookies and edit tokens required (For security
reasons, every Mediawiki edit requires an edit token). The constructor takes two essential parameters, username and
password. Additionally, the server (default wikidata.org), and the token renewal periods can be specified. It's a good
practice to use [Bot password](https://www.mediawiki.org/wiki/Manual:Bot_passwords) instead of simple username and
password, this allows limiting the permissions given to the bot.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')     
```

## Wikibase Data Types ##

Currently, Wikibase supports 17 different data types. The data types are represented as their own classes in
wbi_datatype. Each data types has its specialties, which means that some of them require special parameters (e.g. Globe
Coordinates).

The data types currently implemented:

* wbi_datatype.CommonsMedia
* wbi_datatype.ExternalID
* wbi_datatype.Form
* wbi_datatype.GeoShape
* wbi_datatype.GlobeCoordinate
* wbi_datatype.ItemID
* wbi_datatype.Lexeme
* wbi_datatype.Math
* wbi_datatype.MonolingualText
* wbi_datatype.MusicalNotation
* wbi_datatype.Property
* wbi_datatype.Quantity
* wbi_datatype.Sense
* wbi_datatype.String
* wbi_datatype.TabularData
* wbi_datatype.Time
* wbi_datatype.Url

For details of how to create values (=instances) with these data types, please (for now) consult the docstrings in the
source code. Of note, these data type instances hold the values and, if specified, data type instances for references
and qualifiers. Furthermore, calling the get_value() method of an instance returns either an integer, a string or a
tuple, depending on the complexity of the data type.

# Helper Methods #

## Execute SPARQL queries ##

The method `wbi_item.Item.execute_sparql_query()` allows you to execute SPARQL queries without a hassle. It takes the
actual query string (query), optional prefixes (prefix) if you do not want to use the standard prefixes of Wikidata, the
actual entpoint URL (endpoint), and you can also specify a user agent for the http header sent to the SPARQL server (
user_agent). The latter is very useful to let the operators of the endpoint know who you are, especially if you execute
many queries on the endpoint. This allows the operators of the endpoint to contact you (e.g. specify an email address,
or the URL to your bot code repository.)

## Use Mediawiki API ##

The method `wbi_functions.mediawiki_api_call_helper()` allows you to execute MediaWiki API POST call. It takes a
mandatory data array (data) and multiple optionals parameters like a login object of type wbi_login.Login, a
mediawiki_api_url string if the Mediawiki is not Wikidata, a user_agent string to set a custom HTTP User Agent header,
and an allow_anonymous boolean to force authentication.

Example:

Retrieve last 10 revisions from Wikidata element Q2 (Earth):

```python
from wikibaseintegrator import wbi_functions

query = {
    'action': 'query',
    'prop': 'revisions',
    'titles': 'Q2',
    'rvlimit': 10
}

print(wbi_functions.mediawiki_api_call_helper(query, allow_anonymous=True))
```

## Wikibase search entities ##

The method `wbi_item.Item.search_entities()` allows for string search in a Wikibase instance. This means that labels,
descriptions and aliases can be searched for a string of interest. The method takes five arguments: The actual search
string (search_string), an optional server (mediawiki_api_url, in case the Wikibase instance used is not Wikidata), an
optional user_agent, an optional max_results (default 500), an optional language (default 'en'), and an option
dict_id_label to return a dict of item id and label as a result.

## Merge Wikibase items ##

Sometimes, Wikibase items need to be merged. An API call exists for that, and wbi_core implements a method accordingly.
`wbi_functions.merge_items()` takes five arguments:
the QID of the item which should be merged into another item (from_id), the QID of the item the first item should be
merged into (to_id), a login object of type wbi_login.Login to provide the API call with the required authentication
information, a server (mediawiki_api_url) if the Wikibase instance is not Wikidata and a flag for ignoring merge
conflicts (ignore_conflicts). The last parameter will do a partial merge for all statements which do not conflict. This
should generally be avoided because it leaves a crippled item in Wikibase. Before a merge, any potential conflicts
should be resolved first.

# Examples (in "normal" mode) #

## A Minimal Bot ##

In order to create a minimal bot based on wbi_core, three things are required:

* A login object, as described above.
* A data type object containing a value.
* A ItemEngine object which takes the data, does the checks and performs write.

```python
from wikibaseintegrator import wbi_login
from wikibaseintegrator.entities import item
from wikibaseintegrator.datatypes import basedatatype

# login object
login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = basedatatype.String(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to
data = [entrez_gene_id]

# Search for and then edit/create new item
wd_item = item.Item(data=data)
wd_item.write(login_instance)
```

## A Minimal Bot for Mass Import ##

An enhanced example of the previous bot just puts two of the three things into a 'for loop' and so allows mass creation,
or modification of items.

```python
from wikibaseintegrator import wbi_login
from wikibaseintegrator.entities import item
from wikibaseintegrator.datatypes import basedatatype

# login object
login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
raw_data = {
  '50943': 'ENST00000376197',
  '1029': 'ENST00000498124'
}

for entrez_id, ensembl in raw_data.items():
  # add some references
  references = [
    [
      basedatatype.ItemID(value='Q20641742', prop_nr='P248', is_reference=True),
      basedatatype.Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', is_reference=True),
      basedatatype.ExternalID(value='1017', prop_nr='P351', is_reference=True)
    ]
  ]

  # data type object
  entrez_gene_id = basedatatype.String(value=entrez_id, prop_nr='P351', references=references)
  ensembl_transcript_id = basedatatype.String(value=ensembl, prop_nr='P704', references=references)

  # data goes into a list, because many data objects can be provided to
  data = [entrez_gene_id, ensembl_transcript_id]

  # Search for and then edit/create new item
  wd_item = item.Item(data=data)
  wd_item.write(login_instance)
```

# Examples (in "fast run" mode) #

In order to use the fast run mode, you need to know the property/value combination which determines the data corpus you
would like to operate on. E.g. for operating on human genes, you need to know
that [P351](https://www.wikidata.org/entity/P351) is the NCBI entrez gene ID and you also need to know that you are
dealing with humans, best represented by the [found in taxon property (P703)](https://www.wikidata.org/entity/P703) with
the value [Q15978631](https://www.wikidata.org/entity/Q15978631) for homo sapiens.

IMPORTANT: In order for the fast run mode to work, the data you provide in the constructor must contain at least one
unique value/id only present on one Wikidata item, e.g. an NCBI entrez gene ID, Uniprot ID, etc. Usually, these would be
the same unique core properties used for defining domains in wbi_core, e.g. for genes, proteins, drugs or your custom
domains.

Below, the normal mode run example from above, slightly modified, to meet the requirements for the fast run mode. To
enable it, ItemEngine requires two parameters, fast_run=True/False and fast_run_base_filter which is a dictionary
holding the properties to filter for as keys, and the item QIDs as dict values. If the value is not a QID but a literal,
just provide an empty string. For the above example, the dictionary looks like this:

```python
fast_run_base_filter = {'P351': '', 'P703': 'Q15978631'}
```

The full example:

```python
from wikibaseintegrator import wbi_login
from wikibaseintegrator.entities import item
from wikibaseintegrator.datatypes import basedatatype

# login object
login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')

fast_run_base_filter = {'P351': '', 'P703': 'Q15978631'}
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
      basedatatype.ItemID(value='Q20641742', prop_nr='P248', is_reference=True),
      basedatatype.Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', is_reference=True),
      basedatatype.ExternalID(value='1017', prop_nr='P351', is_reference=True)
    ]
  ]

  # data type object
  entrez_gene_id = basedatatype.String(value=entrez_id, prop_nr='P351', references=references)
  ensembl_transcript_id = basedatatype.String(value=ensembl, prop_nr='P704', references=references)

  # data goes into a list, because many data objects can be provided to
  data = [entrez_gene_id, ensembl_transcript_id]

  # Search for and then edit/create new item
  wd_item = item.Item(data=data, fast_run=fast_run, fast_run_base_filter=fast_run_base_filter)
  wd_item.write(login_instance)
```

Note: Fastrun mode checks for equality of property/value pairs, qualifers (not including qualifier attributes), labels,
aliases and description, but it ignores references by default!
References can be checked in fast run mode by setting `fast_run_use_refs` to `True`.
