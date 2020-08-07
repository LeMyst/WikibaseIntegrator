# Wikibase Integrator #
[![Build Status](https://travis-ci.org/Mystou/WikibaseIntegrator.svg?branch=master)](https://travis-ci.org/Mystou/WikibaseIntegrator)
[![Pyversions](https://img.shields.io/pypi/pyversions/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![PyPi](https://img.shields.io/pypi/v/wikibaseintegrator.svg)](https://pypi.python.org/pypi/wikibaseintegrator)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/Mystou/WikibaseIntegrator/master)

# WikibaseIntegrator / WikidataIntegrator #
WikibaseIntegrator (wbi) is a fork from [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) (wdi) whose purpose is to be focused on Wikibase only.
The main changes are :
* Rename the files from wdi_ to wbi_ to avoid confusion
* Removal of wdi_helpers from the repository
* Removal of references handlers from the repository, but they can still be used with the WDItemEngine

Wikidata is always the default endpoint for all functions.

# Installation #
The easiest way to install WikibaseIntegrator is using `pip` or `pip3`. WikibaseIntegrator supports python 3.6 and higher, hence the suggestion for pip3. If python2 is installed pip will lead to an error indicating missing dependencies. 

```
pip3 install wikibaseintegrator
```

You can also clone the repo and execute with administrator rights or install into a virtualenv.

```bash

git clone https://github.com/Mystou/WikibaseIntegrator.git

cd WikibaseIntegrator

python3 setup.py install
```

To test for correct installation, start a python console and execute the following (Will retrieve the Wikidata item for ['Human'](http://www.wikidata.org/entity/Q5)):

```python
from wikibaseintegrator import wbi_core

my_first_wikidata_item = wbi_core.WDItemEngine(item_id='Q5')

# to check successful installation and retrieval of the data, you can print the json representation of the item
print(my_first_wikidata_item.get_json_representation())
```

# The Core Parts #

wbi_core supports two modes it can be operated in, a normal mode, updating each item at a time and a 'fastrun' mode, which is pre-loading data locally and then just updating items if the new data provided is differing from what is in Wikidata. The latter mode allows for great speedups (measured up to 9x) when tens of thousand of Wikidata 
items need to be checked if they require updates but only a small number will finally be updated, a situation usually encountered when keeping Wikidata in sync with an external resource. 

wbi_core consists of a central class called WDItemEngine and WDLogin for authenticating with Wikidata/Wikipedia.

## wbi_core.WDItemEngine ##
This is the central class which does all the heavy lifting.

Features:

 * Load a Wikidata item based on data to be written (e.g. a unique central identifier)
 * Load a Wikidata item based on its Wikidata item id (aka QID)
 * Checks for conflicts automatically (e.g. multiple items carrying a unique central identifier will trigger an exception)
 * Checks automatically if the correct item has been loaded by comparing it to the data provided
 * All Wikidata data types implemented
 * A dedicated WDItemEngine.write() method allows loading and consistency checks of data before any write to Wikidata is performed
 * Full access to the whole Wikidata item as a JSON document
 * Minimize the number of HTTP requests for reads and writes to improve performance
 * Method to easily execute [SPARQL](query.wikidata.org) queries on the Wikidata endpoint. 
 

There are two ways of working with Wikidata items: 

* A user can provide data, and WDItemEngine will search for and load/modify an existing item or create a new one, solely based on the data provided (preferred). This also performs consistency checks based on a set of SPARQL queries. 
* A user can work with a selected QID to specifically modify the data on the item. This requires that the user knows what he/she is doing and should only be used with great care, as this does not perform consistency checks. 

Examples below illustrate the usage of WDItemEngine.

## wbi_login.WDLogin ##

### Login with username and password ###
In order to write bots for Wikidata, a bot account is required and each script needs to go through a login procedure. For obtaining a bot account in Wikidata,
a specific task needs to be determined and then proposed to the Wikidata community. If the community discussion results in your bot code and account being considered useful for Wikidata, you are ready to go.
However, the code of wbi_core can also run with normal user accounts, the differences are primarily that you have lower writing limits per minute. 

wbi_login.WDLogin provides the login functionality and also stores the cookies and edit tokens required (For security reasons, every Wikidata edit requires an edit token).
The constructor takes two essential parameters, username and password. Additionally, the server (default www.wikidata.org) and the the token renewal periods can be specified. 

```Python     
    login_instance = wbi_login.WDLogin(user='<bot user name>', pwd='<bot password>')     
```

### Login using OAuth1 ###
The Wikimedia universe currently only support authentication via OAuth1. If WDI should be used as a backend for a webapp or the bot should use OAuth for authentication, WDI supports this
You just need to specify consumer token and consumer secret when instantiating wbi_login.WDLogin. In contrast to username and password login, OAuth is a 2 step process as manual user confirmation
for OAuth login is required. This means that the method continue_oath() needs to be called after creating the wbi_login.WDLogin instance.

Example:
```Python     
    login_instance = wbi_login.WDLogin(consumer_token='<your_consumer_token>', pwd='<your_consumer_secret>')
    login_instance.continue_oauth()
```

The method continue_oauth() will either promt the user for a callback URL (normal bot runs) or it will take a parameter so in the case of WDI being
used as a backend for e.g. a web app, where the callback will provide the authentication information directly to the backend and so
 no copy and paste of the callback URL is required.


## Wikidata Data Types ##
Currently, Wikidata supports 17 different data types. The data types are represented as their own classes in wbi_core. Each data type has its specialties, which means that some of them
require special parameters (e.g. Globe Coordinates).

The data types currently implemented:

* wbi_core.WDCommonsMedia
* wbi_core.WDExternalID
* wbi_core.WDForm
* wbi_core.WDGeoShape
* wbi_core.WDGlobeCoordinate
* wbi_core.WDItemID
* wbi_core.WDLexeme
* wbi_core.WDMath
* wbi_core.WDMonolingualText
* wbi_core.WDMusicalNotation
* wbi_core.WDProperty
* wbi_core.WDQuantity
* wbi_core.WDSense
* wbi_core.WDString
* wbi_core.WDTabularData
* wbi_core.WDTime
* wbi_core.WDUrl

For details of how to create values (=instances) with these data types, please (for now) consult the docstrings in the source code. Of note, these data type instances hold the values and, if specified,
data type instances for references and qualifiers. Furthermore, calling the get_value() method of an instance returns either an integer, a string or a tuple, depending on the complexity of the data type.


# Helper Methods #

## Execute SPARQL queries ##
The method wbi_core.WDItemEngine.execute_sparql_query() allows you to execute SPARQL queries without a hassle. It takes the actual
query string (query), optional prefixes (prefix) if you do not want to use the standard prefixes of Wikidata, the actual entpoint URL (endpoint),
 and you can also specify a user agent for the http header sent to the SPARQL server (user_agent). The latter is very useful to let
 the operators of the endpoint know who you are, especially if you execute many queries on the endpoint. This allows the operators of
 the endpoint to contact you (e.g. specify a email address or the URL to your bot code repository.)

## Logging ##
The method wbi_core.WDItemEngine.log() allows for using the Python built in logging functionality to collect errors and other logs.
It takes two parameters, the log level (level) and the log message (message). It is advisable to separate log file columns by colons
and always use the same number of fields, as this allows you to load the log file into databases or dataframes of R or Python.

## Wikidata Search ##
 The method wbi_core.WDItemEngine.get_search_results() allows for string search in
 Wikidata. This means that labels, descriptions and aliases can be searched for a string of interest. The method takes five arguments:
 The actual search string (search_string), an optional server (in case the Wikibase instance used is not Wikidata), an optional user_agent, an
 optional max_results (default 500), and an optional language (default 'en').
 
## Merge Wikidata items ##
Sometimes, Wikidata items need to be merged. An API call exists for that, and wbi_core implements a method accordingly.
`wbi_core.WDItemEngine.merge_items(from_id, to_id, login_obj, server='https://www.wikidata.org', ignore_conflicts='')` takes five
arguments: the QID of the item which should be merged into another item (from_id), the QID of the item the first item should be
merged into (to_id), a login object of type wbi_login.WDLogin() (login_obj) to provide the API call with the required authentication
information, a server (server) if the Wikibase instance is not Wikidata and a flag for ignoring merge conflicts (ignore_conflicts).
The last parameter will do a partial merge for all statements which do not conflict. This should generally be avoided because it 
leaves a crippled item in Wikidata. Before a merge, any potential conflicts should be resolved first.

# Examples (in normal mode) #

## A Minimal Bot ##
In order to create a minimal bot based on wbi_core, three things are required:

* A login object, as described above.
* A data type object containing a value.
* A WDItemEngine object which takes the data, does the checks and performs the write.

```Python

    from wikibaseintegrator import wbi_core, wbi_login
        
    # login object
    login_instance = wbi_login.WDLogin(user='<bot user name>', pwd='<bot password>')
         
    # data type object, e.g. for a NCBI gene entrez ID
    entrez_gene_id = wbi_core.WDString(value='<some_entrez_id>', prop_nr='P351')
    
    # data goes into a list, because many data objects can be provided to 
    data = [entrez_gene_id]
    
    # Search for and then edit/create new item
    wd_item = wbi_core.WDItemEngine(data=data)
    wd_item.write(login_instance)
```

## A Minimal Bot for Mass Import ##
An enhanced example of the previous bot just puts two of the three things into a for loop and so allows mass creation, or modification of WD items.

```Python

    from wikibaseintegrator import wbi_core, wbi_login
        
    # login object
    login_instance = wbi_login.WDLogin(user='<bot user name>', pwd='<bot password>')
    
    # We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
    raw_data = {
        '50943': 'ENST00000376197',
        '1029': 'ENST00000498124'
    }
    
    for entrez_id, ensembl in raw_data.items():
        # data type object
        entrez_gene_id = wbi_core.WDString(value=entrez_id, prop_nr='P351')
        ensembl_transcript_id = wbi_core.WDString(value=ensembl, prop_nr='P704')
        
        # data goes into a list, because many data objects can be provided to 
        data = [entrez_gene_id, ensembl_transcript_id]
        
        # Search for and then edit/create new item
        wd_item = wbi_core.WDItemEngine(data=data)
        wd_item.write(login_instance)
```

# Examples (fast run mode) #
In order to use the fast run mode, you need to know the property/value combination which determines the data corpus you would like to operate on.
E.g. for operating on human genes, you need to know that [P351](http://www.wikidata.org/entity/P351) is the NCBI entrez gene ID and you also need to know that you are dealing with humans, 
best represented by the [found in taxon property (P703)](http://www.wikidata.org/entity/P703) with the value [Q15978631](http://www.wikidata.org/entity/Q15978631) for homo sapiens.

IMPORTANT: In order for the fast run mode to work, the data you provide in the constructor must contain at least one unique value/id only present on one Wikidata item, e.g. an NCBI entrez gene ID, Uniprot ID, etc.
Usually, these would be the same unique core properties used for defining domains in wbi_core, e.g. for genes, proteins, drugs or your custom domains.

Below, the normal mode run example from above, slightly modified, to meet the requirements for the fastrun mode. To enable it, WDItemEngine requires two parameters, fast_run=True/False and fast_run_base_filter which 
 is a dictionary holding the properties to filter for as keys and the item QIDs as dict values. If the value is not a QID but a literal, just provide an empty string. For the above example, the dictionary looks like this:
 
```Python
    fast_run_base_filter = {'P351': '', 'P703': 'Q15978631'}
```
 
The full example:
```Python

    from wikibaseintegrator import wbi_core, wbi_login
        
    # login object
    login_instance = wbi_login.WDLogin(user='<bot user name>', pwd='<bot password>')
    
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
        entrez_gene_id = wbi_core.WDString(value=entrez_id, prop_nr='P351')
        ensembl_transcript_id = wbi_core.WDString(value=ensembl, prop_nr='P704')
        
        # data goes into a list, because many data objects can be provided to 
        data = [entrez_gene_id, ensembl_transcript_id]
        
        # Search for and then edit/create new item
        wd_item = wbi_core.WDItemEngine(data=data, fast_run=fast_run, fast_run_base_filter=fast_run_base_filter)
        wd_item.write(login_instance)
```

Note: Fastrun mode checks for equality of property/value pairs, qualifers (not including qualifier attributes), labels, aliases and description, but it ignores references by default! References can be checked in fastrun mode by setting `fast_run_use_refs` to `True`.
