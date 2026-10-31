# Helpers

## More than Wikibase

WikibaseIntegrator natively supports some extensions:

* MediaInfo entity (beta, see [Structured Data on Commons](mediainfo.md)) - [WikibaseMediaInfo](https://www.mediawiki.org/wiki/Extension:WikibaseMediaInfo)
* EDTF datatype - [Wikibase EDTF](https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF)
* LocalMedia datatype - [Wikibase Local Media](https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media)
* Lexeme entity and datatype - [WikibaseLexeme](https://www.mediawiki.org/wiki/Extension:WikibaseLexeme)

When a Lexeme request (getting or writing a lexeme, form or sense) is sent to a Wikibase instance without lexeme
support, a `wikibaseintegrator.wbi_exceptions.MissingExtensionError` naming the missing WikibaseLexeme extension is
raised, instead of the generic error returned by the API.

## Use MediaWiki API

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

## Execute SPARQL queries

The method `wbi_helpers.execute_sparql_query()` allows you to execute SPARQL queries without a hassle. It takes the
actual query string (query), optional prefixes (prefix) if you do not want to use the standard prefixes of Wikidata, the
actual endpoint URL (endpoint), and you can also specify a user agent for the http header sent to the SPARQL server (
user_agent). The latter is very useful to let the operators of the endpoint know who you are, especially if you execute
many queries on the endpoint. This allows the operators of the endpoint to contact you (e.g. specify an email address,
or the URL to your bot code repository.)

If the SPARQL endpoint is protected, pass the credentials with `auth`, either a `(username, password)` tuple for HTTP
Basic authentication or any `requests.auth.AuthBase` instance, or add your own HTTP headers with `headers`. To set the
credentials once for every query, including the ones executed by the fast run mode, use `wbi_config['SPARQL_AUTH']`:

```python
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.wbi_config import config as wbi_config

query = 'SELECT ?item WHERE { ?item ?p ?o . } LIMIT 1'

wbi_helpers.execute_sparql_query(query, auth=('username', 'password'))
wbi_helpers.execute_sparql_query(query, headers={'Authorization': 'Bearer <token>'})

wbi_config['SPARQL_AUTH'] = ('username', 'password')
wbi_helpers.execute_sparql_query(query)
```

### Wikimedia Commons Query Service

The SPARQL endpoint of Structured Data on Commons, the [Wikimedia Commons Query Service](https://commons-query.wikimedia.org/)
(WCQS), authenticates with a long-lived `wcqsOauth` cookie. There is no API to get it: copy it from a web browser logged
in to WCQS, as explained in [Commons:SPARQL query service/API endpoint](https://commons.wikimedia.org/wiki/Commons:SPARQL_query_service/API_endpoint).
`wbi_login.WCQSAuth` sends it, and keeps the short-lived session cookie WCQS sets in return:

```python
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_login import WCQSAuth

wbi_config['SPARQL_ENDPOINT_URL'] = 'https://commons-query.wikimedia.org/sparql'
wbi_config['WIKIBASE_URL'] = 'https://commons.wikimedia.org'
# Every query, including the ones of the fast run mode, is authenticated
wbi_config['SPARQL_AUTH'] = WCQSAuth('<wcqsOauth cookie>')

wbi_helpers.execute_sparql_query('SELECT ?file WHERE { ?file wdt:P180 wd:Q146 } LIMIT 10')
```

An invalid or revoked cookie raises a `WCQSAuthenticationError`, instead of being retried.

## Wikibase search entities

The method `wbi_helpers.search_entities()` allows for string search in a Wikibase instance, using the labels and aliases
of the entities. It takes the search string (search_string) and optional parameters: the language of the search
(language, default `wbi_config['DEFAULT_LANGUAGE']`), strict_language to disable the language fallback, the type of
entity to search (search_type: item, property, lexeme, form, sense or mediainfo, default item), the maximum number of
results (max_results, default 50, higher values trigger additional paginated calls) and dict_result to return detailed
dictionaries instead of a list of IDs. Like the other helpers, it also accepts `mediawiki_api_url`, `login`, `user_agent`,
etc.

```python
from wikibaseintegrator import wbi_helpers

print(wbi_helpers.search_entities(search_string='Earth', max_results=5))
```

## Write a single statement

`wbi_helpers.set_claim()` creates or replaces a single statement, with its qualifiers and references, without loading
or writing the whole entity. It is useful for large entities, and the edit doesn't conflict with the edits of the other
statements. A claim with an ID replaces the statement with this ID. A claim without an ID is added to the entity given by
entity_id, and the ID generated for it is set on the claim once the edit is saved. It also accepts the index of the
statement in the list of statements of the entity (index), baserevid, summary, tags, is_bot and
ignore_duplicate_mainsnak, which doesn't save the statement if the entity already has one with the same main snak.
To delete a statement, use `wbi_helpers.remove_claims()` with its ID.

```python
from wikibaseintegrator import wbi_helpers, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Time

login = wbi_login.Login(user='<bot user name>', password='<bot password>')

claim = ExternalID(prop_nr='P214', value='113230702', references=[[Time(prop_nr='P813', time='now')]])
wbi_helpers.set_claim(claim, entity_id='Q42', login=login)
print(claim.id)  # The ID of the new statement, e.g. Q42$1c5e2f6b-...

claim.mainsnak.datavalue['value'] = '113230703'
wbi_helpers.set_claim(claim, login=login)  # Replace the statement
```

## Merge Wikibase items

Sometimes, Wikibase items need to be merged. An API call exists for that, and `wbi_helpers.merge_items()` implements it.
It takes these arguments:

* the QID of the item which should be merged into another item (from_id)
* the QID of the item the first item should be merged into (to_id)
* a login object of type wbi_login.Login to provide the API call with the required authentication information
* a list of elements to ignore conflicts for (ignore_conflicts), which can contain `'description'`, `'sitelink'` and
  `'statement'`. This will do a partial merge for the elements which do not conflict and should generally be avoided
  because it leaves a crippled item in Wikibase. Before a merge, any potential conflicts should be resolved first.
* a boolean if the changes need to be marked as made by a bot (is_bot)
* a list of change tags to apply to the revision (tags)

Wikibase turns the emptied item into a redirect to the target item, so there is no need to create the redirect
separately.

To turn an item into a redirect without merging it, `wbi_helpers.create_redirect()` takes the same from_id, to_id,
login and is_bot arguments. The source item must be empty, deleted or already a redirect (to change its target, for
example to fix a double redirect), and the target item must exist and not be a redirect itself.

```python
from wikibaseintegrator import wbi_helpers, wbi_login

login = wbi_login.Login(user='<bot user name>', password='<bot password>')
wbi_helpers.create_redirect(from_id='Q30', to_id='Q5', login=login)  # Q30 now redirects to Q5
```

To merge more than two items at once, `wbi_helpers.merge_multiple_items()` takes a list of QIDs and merges all of them
into the one with the lowest numeric ID, which it returns. It accepts the same login, ignore_conflicts, is_bot and tags
arguments. The merges are done one by one: if one fails, its exception is raised and the merges already done are kept.

```python
from wikibaseintegrator import wbi_helpers, wbi_login

login = wbi_login.Login(user='<bot user name>', password='<bot password>')
to_id = wbi_helpers.merge_multiple_items(['Q100', 'Q30', 'Q5'], login=login)  # Q30 and Q100 are merged into Q5
```

## Check a Wikibase instance

`check_wikibase()` reports the features of a Wikibase instance: the MediaWiki version, the installed extensions, the
entity types and the datatypes it supports, and whether the SPARQL endpoint answers. It also checks that
`config['WIKIBASE_URL']` matches the concept URIs of the instance, as the SPARQL queries built by WikibaseIntegrator
(fast run mode, ...) rely on it.

```python
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_helpers import check_wikibase

wbi_config['MEDIAWIKI_API_URL'] = 'https://my-wikibase.example.org/w/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://my-wikibase.example.org/query/sparql'
wbi_config['WIKIBASE_URL'] = 'https://my-wikibase.example.org'

result = check_wikibase()
print(result)  # A readable report, with the problems found

if not result.has_lexemes:
    print('This instance does not support lexemes')
```

The result also provides `has_mediainfo`, `has_search` (WikibaseCirrusSearch, needed by the `haswbstatement` search
keyword), `has_quality_constraints` (needed by `check_constraints()`), `extensions`, `entity_types`, `datatypes` and
`problems`.

## Parse values

`wbi_helpers.parse_value()` parses values written as text, like `'3 March 1850'`, `'1850s'` or `'12±0.5'`, into data
values, with the parsers of the Wikibase instance (wbparsevalue API). It is useful to import data from files without
parsing the dates, their precision or the quantities yourself. It takes one value or a list of values, and either the
datatype of the values (datatype, e.g. `'time'`, `'quantity'`, `'globe-coordinate'`) or a property whose datatype is used
(prop_nr). The options of the parser (options, e.g. `{'lang': 'fr'}` for dates written in French) and a validation of the
parsed values (validate) are optional.

It returns one result per value, in the same order. A value which can't be parsed doesn't raise an exception: its result
has an `'error'` key, so that all the values can be checked at once.

```python
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.datatypes import Time

for result in wbi_helpers.parse_value(['3 March 1850', '1850s', 'not a date'], datatype='time'):
    if 'error' in result:
        print(f"Can't parse {result['raw']}")
    else:
        claim = Time(prop_nr='P569', **result['value'])  # A time value has the arguments of Time()
```

## Other helpers

`wbi_helpers` also provides:

* `merge_lexemes()`: merge two lexemes.
* `remove_claims()`: delete a claim from an entity by its claim ID.
* `check_constraints()`: check the constraint violations of entities or claims with the WikibaseQualityConstraints
  extension.
* `fulltext_search()`: perform a fulltext search on the MediaWiki instance.
* `get_available_badges()`: list the items which can be used as badges of sitelinks, e.g.
  `item.sitelinks.set('enwiki', 'Douglas Adams', badges=['Q17437796'])` (featured article on Wikidata).
* `delete_page()`: delete a page.
* `download_entity_ttl()`: download the RDF (Turtle) representation of an entity.

Some examples are available in the [wbi_helpers.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/wbi_helpers.ipynb) notebook.

## Track the edits with EditGroups

[EditGroups](https://www.wikidata.org/wiki/Wikidata:Edit_groups) tracks the edits of a bot on Wikidata as a batch,
which can be reviewed, discussed and reverted at once. An edit is part of a batch when its summary ends with a link to
the batch, which `EditGroup` generates:

```python
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item
from wikibaseintegrator.wbi_editgroups import EditGroup

wbi = WikibaseIntegrator(login=login_instance)

# One EditGroup per batch, with a random batch ID
editgroup = EditGroup()
print(editgroup.url)  # https://editgroups.toolforge.org/b/CB/<batch ID>/

for qid in ['Q582', 'Q90']:
    item = wbi.item.get(qid)
    item.claims.add(Item(value='Q484170', prop_nr='P31'))
    # "Add instance of ([[:toolforge:editgroups/b/CB/<batch ID>|details]])"
    item.write(summary=editgroup.summary('Add instance of'))
```

To add edits to an existing batch, for example after a restart of the bot, pass its ID: `EditGroup('89ead4fe')`. A
summary that is too long is shortened, so that the link is never truncated.
