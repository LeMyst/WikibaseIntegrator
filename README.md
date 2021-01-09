# Wikibase Integrator #

![Python package](https://github.com/LeMyst/WikibaseIntegrator/workflows/Python%20package/badge.svg)
![CodeQL](https://github.com/LeMyst/WikibaseIntegrator/workflows/CodeQL/badge.svg)
[![Pyversions](https://img.shields.io/pypi/pyversions/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![PyPi](https://img.shields.io/pypi/v/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)

- [WikibaseIntegrator / WikidataIntegrator](#wikibaseintegrator---wikidataintegrator)
  * [Move from WikidataIntegrator to WikibaseIntegrator](#move-from-wikidataintegrator-to-wikibaseintegrator)
- [Installation](#installation)
- [The Core Parts](#the-core-parts)
  * [wbi_core.ItemEngine](#wbi-coreitemengine)
  * [wbi_core.FunctionsEngine](#wbi-corefunctionsengine)
  * [wbi_login.Login](#wbi-loginlogin)
    + [Login with a username and a password](#login-with-a-username-and-a-password)
    + [Login using OAuth1](#login-using-oauth1)
  * [Wikibase Data Types](#wikibase-data-types)
- [Helper Methods](#helper-methods)
  * [Execute SPARQL queries](#execute-sparql-queries)
  * [Wikidata Search](#wikidata-search)
  * [Merge Wikibase items](#merge-wikibase-items)
- [Examples (in "normal" mode)](#examples--in--normal--mode-)
  * [A Minimal Bot](#a-minimal-bot)
  * [A Minimal Bot for Mass Import](#a-minimal-bot-for-mass-import)
- [Examples (in "fast run" mode)](#examples--in--fast-run--mode-)

# WikibaseIntegrator / WikidataIntegrator #

WikibaseIntegrator (wbi) is a fork from [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) (wdi) whose
purpose is to be focused on Wikibase compatibility. The main changes are :

* Rename the files from wdi_ to wbi_ to avoid confusion
* Removal of wdi_helpers from the repository
* Removal of references handlers from the repository, but they can still be used with the ItemEngine

Wikidata is always the default endpoint for all functions.

## Move from WikidataIntegrator to WikibaseIntegrator ##

* Module name changes :
    * wdi_backoff -> wbi_backoff
    * wdi_config -> wbi_config
    * wdi_core -> wbi_core
    * wdi_fastrun -> wbi_fastrun
    * wdi_login -> wbi_login
* Classe name changes:
    * WDLogin -> Login
    * WDItemEngine -> ItemEngine
    * WDBaseDataType -> BaseDataType
    * WDCommonsMedia -> CommonsMedia
    * WDExternalID -> ExternalID
    * WDForm -> Form
    * WDGeoShape -> GeoShape
    * WDGlobeCoordinate -> GlobeCoordinate
    * WDItemID -> ItemID
    * WDLexeme -> Lexeme
    * WDMath -> Math
    * WDMonolingualText -> MonolingualText
    * WDMusicalNotation -> MusicalNotation
    * WDProperty -> Property
    * WDQuantity -> Quantity
    * WDSense -> Sense
    * WDString -> String
    * WDTabularData -> TabularData
    * WDTime -> Time
    * WDUrl -> Url
* ItemEngine parameter changes:
    * wd_item_id -> item_id
* ItemEngine attribute changes:
    * wd_item_id -> item_id
* Change wbi_core.set_aliases parameter named 'append' to 'if_exists' with a value of APPEND (default) or REPLACE
* Remove CONCEPT_BASE_URI wbi_config option and classes' parameter. It's now derived from WIKIBASE_URL.
* wbi_core.log() has been removed. Please use your own logging implementation.

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

python setup.py install
```

To test for correct installation, start a Python console and execute the following (Will retrieve the Wikidata item
for ['Human'](https://www.wikidata.org/entity/Q5)):

```python
from wikibaseintegrator import wbi_core

my_first_wikidata_item = wbi_core.ItemEngine(item_id='Q5')

# to check successful installation and retrieval of the data, you can print the json representation of the item
print(my_first_wikidata_item.get_json_representation())
```

# The Core Parts #

wbi_core supports two modes it can be operated in, a normal mode, updating each item at a time and, a fast run mode,
which is pre-loading data locally and then just updating items if the new data provided is differing from what is in
Wikidata. The latter mode allows for great speedups (measured up to 9x) when tens of thousand of Wikidata items need to
be checked if they require updates but only a small number will finally be updated, a situation usually encountered when
keeping Wikidata in sync with an external resource.

wbi_core consists of a central class called ItemEngine and Login for authenticating with a MediaWiki isntance (like
Wikidata).

## wbi_core.ItemEngine ##

This is the central class which does all the heavy lifting.

Features:

* Load a Wikibase item based on data to be written (e.g. a unique central identifier)
* Load a Wikibase item based on its Wikibase item id (aka QID)
* Checks for conflicts automatically (e.g. multiple items carrying a unique central identifier will trigger an
  exception)
* Checks automatically if the correct item has been loaded by comparing it to the data provided
* All Wikibase data types implemented
* A dedicated ItemEngine.write() method allows loading and consistency checks of data before any write to Wikibase is
  performed
* Full access to the whole Wikibase item as a JSON document

There are two ways of working with Wikibase items:

* A user can provide data, and ItemEngine will search for and load/modify an existing item or create a new one, solely
  based on the data provided (preferred). This also performs consistency checks based on a set of SPARQL queries.
* A user can work with a selected QID to specifically modify the data on the item. This requires that the user knows
  what he/she is doing and should only be used with great care, as this does not perform consistency checks.

Examples below illustrate the usage of ItemEngine.

## wbi_core.FunctionsEngine ##

wbi_core.FunctionsEngine provides a set of static functions to request or manipulate data from MediaWiki API or SPARQL
Service.

Features:

* Minimize the number of HTTP requests for reads and writes to improve performance
* Method to easily execute [SPARQL](https://query.wikidata.org) queries on the Wikibase SPARQL endpoint.

## wbi_login.Login ##

### Login with a username and a password ###

wbi_login.Login provides the login functionality and also stores the cookies and edit tokens required (For security
reasons, every Mediawiki edit requires an edit token). The constructor takes two essential parameters, username and
password. Additionally, the server (default wikidata.org), and the token renewal periods can be specified.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')     
```

### Login using OAuth1 ###

The Wikimedia universe currently only support authentication via OAuth1. If WBI should be used as a backend for a
webapp, the bot should use OAuth for authentication, WBI supports this, you just need to specify consumer key and
consumer secret when instantiating wbi_login.Login. In contrast to username and password login, OAuth is a 2 steps
process as manual user confirmation for OAuth login is required. This means that the method continue_oauth() needs to be
called after creating the wbi_login.Login instance.

Example:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(consumer_key='<your_consumer_key>', consumer_secret='<your_consumer_secret>')
login_instance.continue_oauth()
```

The method continue_oauth() will either prompt the user for a callback URL (normal bot runs), or it will take a
parameter so in the case of WBI being used as a backend for e.g. a web app, where the callback will provide the
authentication information directly to the backend and so no copy and paste of the callback URL is required.

## Wikibase Data Types ##

Currently, Wikibase supports 17 different data types. The data types are represented as their own classes in wbi_core.
Each data type has its specialties, which means that some of them require special parameters (e.g. Globe Coordinates).

The data types currently implemented:

* wbi_core.CommonsMedia
* wbi_core.ExternalID
* wbi_core.Form
* wbi_core.GeoShape
* wbi_core.GlobeCoordinate
* wbi_core.ItemID
* wbi_core.Lexeme
* wbi_core.Math
* wbi_core.MonolingualText
* wbi_core.MusicalNotation
* wbi_core.Property
* wbi_core.Quantity
* wbi_core.Sense
* wbi_core.String
* wbi_core.TabularData
* wbi_core.Time
* wbi_core.Url

For details of how to create values (=instances) with these data types, please (for now) consult the docstrings in the
source code. Of note, these data type instances hold the values and, if specified, data type instances for references
and qualifiers. Furthermore, calling the get_value() method of an instance returns either an integer, a string or a
tuple, depending on the complexity of the data type.

# Helper Methods #

## Execute SPARQL queries ##

The method wbi_core.ItemEngine.execute_sparql_query() allows you to execute SPARQL queries without a hassle. It takes
the actual query string (query), optional prefixes (prefix) if you do not want to use the standard prefixes of Wikidata,
the actual entpoint URL (endpoint), and you can also specify a user agent for the http header sent to the SPARQL
server (user_agent). The latter is very useful to let the operators of the endpoint know who you are, especially if you
execute many queries on the endpoint. This allows the operators of the endpoint to contact you (e.g. specify an email
address, or the URL to your bot code repository.)

## Wikidata Search ##

The method wbi_core.ItemEngine.get_search_results() allows for string search in a Wikibase instance. This means that
labels, descriptions and aliases can be searched for a string of interest. The method takes five arguments: The actual
search string (search_string), an optional server (mediawiki_api_url, in case the Wikibase instance used is not
Wikidata), an optional user_agent, an optional max_results (default 500), an optional language (default 'en'), and an
option dict_id_label to return a dict of item id and label as a result.

## Merge Wikibase items ##

Sometimes, Wikibase items need to be merged. An API call exists for that, and wbi_core implements a method accordingly.
`wbi_core.ItemEngine.merge_items(from_id, to_id, login_obj)` takes five arguments:
the QID of the item which should be merged into another item (from_id), the QID of the item the first item should be
merged into (to_id), a login object of type wbi_login.Login() to provide the API call with the required authentication
information, a server (mediawiki_api_url) if the Wikibase instance is not Wikidata and a flag for ignoring merge
conflicts (ignore_conflicts). The last parameter will do a partial merge for all statements which do not conflict. This
should generally be avoided because it leaves a crippled item in Wikibase. Before a merge, any potential conflicts
should be resolved first.

# Examples (in "normal" mode) #

## A Minimal Bot ##

In order to create a minimal bot based on wbi_core, three things are required:

* A login object, as described above.
* A data type object containing a value.
* A ItemEngine object which takes the data, does the checks and performs the write.

```python
from wikibaseintegrator import wbi_core, wbi_login

# login object
login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = wbi_core.String(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to 
data = [entrez_gene_id]

# Search for and then edit/create new item
wd_item = wbi_core.ItemEngine(data=data)
wd_item.write(login_instance)
```

## A Minimal Bot for Mass Import ##

An enhanced example of the previous bot just puts two of the three things into a for loop and so allows mass creation,
or modification of items.

```python
from wikibaseintegrator import wbi_core, wbi_login

# login object
login_instance = wbi_login.Login(user='<bot user name>', pwd='<bot password>')

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
raw_data = {
    '50943': 'ENST00000376197',
    '1029': 'ENST00000498124'
}

for entrez_id, ensembl in raw_data.items():
    # data type object
    entrez_gene_id = wbi_core.String(value=entrez_id, prop_nr='P351')
    ensembl_transcript_id = wbi_core.String(value=ensembl, prop_nr='P704')

    # data goes into a list, because many data objects can be provided to 
    data = [entrez_gene_id, ensembl_transcript_id]

    # add one reference
    references = [
        [
            wbi_core.ItemID(value='Q20641742', prop_nr='P248', is_reference=True),
            wbi_core.Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', is_reference=True),
            wbi_core.ExternalID(value='1017', prop_nr='P351', is_reference=True)
        ]
    ]

    # Search for and then edit/create new item
    wd_item = wbi_core.ItemEngine(data=data, references=references)
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
from wikibaseintegrator import wbi_core, wbi_login

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
    # data type object
    entrez_gene_id = wbi_core.String(value=entrez_id, prop_nr='P351')
    ensembl_transcript_id = wbi_core.String(value=ensembl, prop_nr='P704')

    # data goes into a list, because many data objects can be provided to 
    data = [entrez_gene_id, ensembl_transcript_id]

    # add one reference
    references = [
        [
            wbi_core.ItemID(value='Q20641742', prop_nr='P248', is_reference=True),
            wbi_core.Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', is_reference=True),
            wbi_core.ExternalID(value='1017', prop_nr='P351', is_reference=True)
        ]
    ]

    # Search for and then edit/create new item
    wd_item = wbi_core.ItemEngine(data=data, references=references, fast_run=fast_run,
                                  fast_run_base_filter=fast_run_base_filter)
    wd_item.write(login_instance)
```

Note: Fastrun mode checks for equality of property/value pairs, qualifers (not including qualifier attributes), labels,
aliases and description, but it ignores references by default!
References can be checked in fast run mode by setting `fast_run_use_refs` to `True`.
