# Migrating from WikidataIntegrator

WikibaseIntegrator started as a fork of [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator), whose last
release is 0.9.30 (June 2023). The concepts are the same (entities, data types, references, qualifiers, the fast run
mode), but the API was rewritten in v0.12: there is no compatibility layer, so a WikidataIntegrator script has to be
adapted. This page maps the WikidataIntegrator 0.9.30 API to WikibaseIntegrator.

## Installation

```bash
python -m pip uninstall wikidataintegrator
python -m pip install wikibaseintegrator
```

WikibaseIntegrator requires Python 3.11 or newer.

## A script, before and after

A bot updating an existing item, with WikidataIntegrator:

```python
from wikidataintegrator import wdi_core, wdi_login

login = wdi_login.WDLogin(user='MyUsername@MyBot', pwd='<bot password>')

references = [[
    wdi_core.WDItemID(value='Q20641742', prop_nr='P248', is_reference=True),
    wdi_core.WDTime('+2020-02-08T00:00:00Z', prop_nr='P813', is_reference=True),
]]

data = [
    wdi_core.WDExternalID(value='50943', prop_nr='P351', references=references),
    wdi_core.WDItemID(value='Q7187', prop_nr='P31', references=references),
]

# The values of P351 replace the existing ones, the P31 value is appended (append_value)
item = wdi_core.WDItemEngine(wd_item_id='Q14911732', data=data, append_value=['P31'])
item.set_label('FOXP3', lang='en')
qid = item.write(login, edit_summary='Update from NCBI Gene')
```

The same bot with WikibaseIntegrator:

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Item, Time
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists

# Wikimedia asks every tool to identify itself: https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
config['USER_AGENT'] = 'MyBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

login = wbi_login.Login(user='MyUsername@MyBot', password='<bot password>')
wbi = WikibaseIntegrator(login=login)

# No is_reference: a reference is a list of claims, references a list of references
references = [[
    Item(value='Q20641742', prop_nr='P248'),
    Time(time='+2020-02-08T00:00:00Z', prop_nr='P813'),
]]

item = wbi.item.get('Q14911732')
item.claims.add(ExternalID(value='50943', prop_nr='P351', references=references), action_if_exists=ActionIfExists.REPLACE_ALL)
item.claims.add(Item(value='Q7187', prop_nr='P31', references=references))  # APPEND_OR_REPLACE by default
item.labels.set('en', 'FOXP3')
item = item.write(summary='Update from NCBI Gene')
qid = item.id
```

The main differences:

* The entity is loaded first (`wbi.item.get()`, or `wbi.item.new()` for a new item), then modified, then written.
  Nothing is sent to the instance before `write()`.
* `write()` returns the written entity, not its ID: the ID is `item.id`.
* The login is given once to `WikibaseIntegrator(login=...)` (or to each `write(login=...)`).
* The arguments are named: `labels.set(language, value)` takes the language first, `set_label(label, lang)` took it last.

## Entities

| WikidataIntegrator                                          | WikibaseIntegrator                                                                      |
|:------------------------------------------------------------|:----------------------------------------------------------------------------------------|
| `WDItemEngine(wd_item_id='Q42')`                            | `wbi.item.get('Q42')`                                                                   |
| `WDItemEngine(new_item=True)`                               | `wbi.item.new()`                                                                        |
| `WDItemEngine(data=data)` without `wd_item_id`              | No automatic search, see [Finding an item from its data](#finding-an-item-from-its-data) |
| `WDItemEngine(item_data=json)`                              | `wbi.item.new().from_json(json)`                                                        |
| `WDItemEngine(..., search_only=True)` then `update(data)`   | `wbi.item.get()` then `item.claims.add(data)`: nothing is written before `write()`      |
| `item.write(login, edit_summary='...', bot_account=True)`   | `item.write(login=login, summary='...', is_bot=True)`                                   |
| `write(..., entity_type='property', property_datatype='string')` | `wbi.property.new(datatype='string')` then `write()`                               |
| `item.get_wd_json_representation()`                         | `item.get_json()`                                                                       |
| `item.lastrevid`, `item.wd_item_id`                         | `item.lastrevid`, `item.id`                                                             |
| `item.get_label('en')`, `set_label('Label', lang='en')`     | `item.labels.get('en').value`, `item.labels.set('en', 'Label')`                         |
| `item.get_description('en')`, `set_description(...)`        | `item.descriptions.get('en').value`, `item.descriptions.set('en', '...')`               |
| `item.get_aliases('en')`                                    | `[alias.value for alias in item.aliases.get('en')]`                                     |
| `item.set_aliases(['A', 'B'], lang='en')` (append)          | `item.aliases.add('en', ['A', 'B'])`                                                    |
| `item.set_aliases(['A', 'B'], lang='en', append=False)`     | `item.aliases.set('en', ['A', 'B'], action_if_exists=ActionIfExists.REPLACE_ALL)`       |
| `item.get_sitelink('enwiki')`, `set_sitelink(site, title, badges)` | `item.sitelinks.get('enwiki')`, `item.sitelinks.set(site, title, badges)`        |
| `WDItemEngine.generate_item_instances(['Q1', 'Q2'])`        | `wbi_helpers.generate_entity_instances(['Q1', 'Q2'])`                                   |
| `sdc_core.WDItemEngine` (Commons)                           | `wbi.mediainfo.get('M75908279')`, see [Structured Data on Commons](mediainfo.md)        |

WikibaseIntegrator also reads and writes properties (`wbi.property`), lexemes with their forms and senses
(`wbi.lexeme`) and MediaInfo entities (`wbi.mediainfo`). See [Entities](entities.md).

## Data types

The data types lose their `WD` prefix and are imported from `wikibaseintegrator.datatypes`. Their arguments are named:

| WikidataIntegrator                                        | WikibaseIntegrator                                                     |
|:----------------------------------------------------------|:-----------------------------------------------------------------------|
| `WDString(value, prop_nr)`                                | `String(value=..., prop_nr=...)`                                       |
| `WDItemID`, `WDProperty`, `WDLexeme`, `WDForm`, `WDSense` | `Item`, `Property`, `Lexeme`, `Form`, `Sense`                          |
| `WDExternalID`, `WDUrl`, `WDCommonsMedia`, `WDMath`       | `ExternalID`, `URL`, `CommonsMedia`, `Math`                            |
| `WDGeoShape`, `WDTabularData`, `WDMusicalNotation`        | `GeoShape`, `TabularData`, `MusicalNotation`                           |
| `WDMonolingualText(value, prop_nr, language='en')`        | `MonolingualText(text=..., prop_nr=..., language='en')`                |
| `WDQuantity(value, prop_nr, upper_bound, lower_bound, unit)` | `Quantity(amount=..., prop_nr=..., upper_bound=..., lower_bound=..., unit=...)` |
| `WDTime(time, prop_nr, precision=11, timezone, calendarmodel)` | `Time(time=..., prop_nr=..., precision=WikibaseTimePrecision.DAY, timezone=..., calendarmodel=...)` |
| `WDGlobeCoordinate(latitude, longitude, precision, prop_nr, globe)` | `GlobeCoordinate(latitude=..., longitude=..., precision=..., prop_nr=..., globe=...)` |
| `WDEDTF`, `WDLocalMedia`                                  | `EDTF`, `LocalMedia`, from `wikibaseintegrator.datatypes.extra`        |
| —                                                         | `EntitySchema`                                                         |

The other arguments:

| WikidataIntegrator                             | WikibaseIntegrator                                                                        |
|:-----------------------------------------------|:------------------------------------------------------------------------------------------|
| `is_reference=True`, `is_qualifier=True`       | Removed: the same classes are used for claims, qualifiers and references                  |
| `references=[[WDItemID(..., is_reference=True)]]` | `references=[[Item(...)]]`, or a `References` object                                   |
| `qualifiers=[WDString(..., is_qualifier=True)]` | `qualifiers=Qualifiers()` with `qualifiers.add(String(...))`, or a list of claims        |
| `rank='preferred'`                             | `rank=WikibaseRank.PREFERRED`                                                             |
| `snak_type='somevalue'`, `snak_type='novalue'` | `snaktype=WikibaseSnakType.UNKNOWN_VALUE`, `snaktype=WikibaseSnakType.NO_VALUE`           |
| `check_qualifier_equality=False`               | No equivalent: two claims are equal when they have the same property, value and qualifiers |
| `stat.get_value()`, `stat.get_prop_nr()`       | `claim.mainsnak.datavalue['value']`, `claim.mainsnak.property_number`                     |

The enumerations (`WikibaseRank`, `WikibaseSnakType`, `WikibaseTimePrecision`, `ActionIfExists`...) are in
`wikibaseintegrator.wbi_enums`. See [Data types](datatypes.md).

## Writing statements

WikidataIntegrator took all the statements in the `data` list of the constructor and merged them with the item.
WikibaseIntegrator adds them with `item.claims.add(claims, action_if_exists=...)`, where `action_if_exists` says what
to do with the existing statements of the same property:

| WikidataIntegrator                                         | WikibaseIntegrator                                                        |
|:-----------------------------------------------------------|:--------------------------------------------------------------------------|
| A property in `data` (the default): its other values are removed | `ActionIfExists.REPLACE_ALL`                                        |
| A property in `append_value`: the value is added if missing | `ActionIfExists.APPEND_OR_REPLACE` (the default of `claims.add()`)       |
| A data type with an empty value (`WDString('', 'P31')`): the property is removed | `item.claims.remove('P31')`                         |
| `WDFunctionsEngine.delete_statement(statement_id, revision, login)` | `item.claims.get('P31')[0].remove()` then `write()`, or `wbi_helpers.remove_claims(claim_id, login=login)` |
| `update(data, append_value=[...])`                         | More `item.claims.add()` calls                                            |

The reference handling is different. WikidataIntegrator merged the references of a statement already present
following `global_ref_mode` (`KEEP_GOOD` by default), and kept the statements with "good" references
(`keep_good_ref_statements`, `good_refs`). WikibaseIntegrator has no notion of good references, and its actions
handle the references of a statement already present (same property, value and qualifiers) as follows:

| WikidataIntegrator `global_ref_mode` | WikibaseIntegrator                                                                               |
|:-------------------------------------|:-------------------------------------------------------------------------------------------------|
| `STRICT_OVERWRITE`                   | `APPEND_OR_REPLACE`: the references of the new claim, if it has some, replace the existing ones   |
| `STRICT_KEEP_APPEND`                 | `MERGE_REFS_OR_APPEND`: the references missing from the existing statement are added             |
| `STRICT_KEEP`                        | `REPLACE_ALL` or `KEEP` leave the existing statement as it is                                    |
| `KEEP_GOOD`, `CUSTOM` (`ref_handler`) | No equivalent: get the existing statement with `item.claims.get()` and edit its `references`    |

`REPLACE_ALL` keeps the statements already present as they are, references included. To remove the other values of a
property **and** add the new references to the statements already present, add the claims twice:

```python
item.claims.add(data, action_if_exists=ActionIfExists.REPLACE_ALL)  # remove the other values of the properties
item.claims.add(data, action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)  # add the new references
```

## Finding an item from its data

Without `wd_item_id`, WikidataIntegrator searched the item holding the values of `data` for the properties with a
distinct-values constraint (`core_props`, `core_prop_match_thresh`), and created a new item if none was found.
WikibaseIntegrator doesn't search automatically: find the item yourself, for example with the fast run container,
which resolves the item from a unique value with a SPARQL query:

```python
from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import ExternalID, Item

base_filter = [ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')]
frc = wbi_fastrun.get_fastrun_container(base_filter=base_filter)

qids = frc.get_entities(claims=[ExternalID(value='50943', prop_nr='P351')])
item = wbi.item.get(qids[0]) if qids else wbi.item.new()
```

or with the search of the MediaWiki API, which supports the `haswbstatement` keyword on Wikidata:

```python
from wikibaseintegrator import wbi_helpers

results = wbi_helpers.fulltext_search('haswbstatement:P351=50943')
```

## Fast run

| WikidataIntegrator                                            | WikibaseIntegrator                                                         |
|:--------------------------------------------------------------|:---------------------------------------------------------------------------|
| `WDItemEngine(data=data, fast_run=True, fast_run_base_filter={'P351': '', 'P703': 'Q15978631'})` | `item.claims.add(data)` then `item.write_required(base_filter=[ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')])` |
| `item.require_write`                                          | The value returned by `item.write_required()`                              |
| `fast_run_use_refs=True`                                      | `write_required(..., use_references=True)`                                 |
| `fast_run_case_insensitive=True`                              | `write_required(..., case_insensitive=True)`                               |

The base filter is a list of data type instances instead of a dictionary: a value is a required value, no value means
any value. It also supports property paths. See [Fast run](fastrun.md).

## Login

| WikidataIntegrator                                                 | WikibaseIntegrator                                                         |
|:-------------------------------------------------------------------|:---------------------------------------------------------------------------|
| `WDLogin(user='User@Bot', pwd='<bot password>')`                   | `wbi_login.Login(user='User@Bot', password='<bot password>')`              |
| `WDLogin(user, pwd, use_clientlogin=True)`                         | `wbi_login.Clientlogin(user=..., password=...)`                            |
| `WDLogin(consumer_key=..., consumer_secret=...)` then `continue_oauth()` | `wbi_login.OAuth1(consumer_token=..., consumer_secret=...)` then `continue_oauth()` |
| —                                                                  | `wbi_login.OAuth2(consumer_token=..., consumer_secret=...)` for an owner-only consumer, the recommended way for a bot |
| —                                                                  | `wbi_login.OAuth1(consumer_token=..., consumer_secret=..., access_token=..., access_secret=...)` for an owner-only OAuth 1.0a consumer |

See [Login](login.md).

## Helpers

`WDFunctionsEngine` and the static methods of `WDItemEngine` become functions of `wikibaseintegrator.wbi_helpers`:

| WikidataIntegrator                                           | WikibaseIntegrator                                                     |
|:-------------------------------------------------------------|:-----------------------------------------------------------------------|
| `execute_sparql_query(query, prefix, endpoint, user_agent)`  | `wbi_helpers.execute_sparql_query(query, prefix, endpoint, user_agent)` |
| `execute_sparql_query(..., as_dataframe=True)`               | No equivalent: build the dataframe from `results['results']['bindings']` |
| `mediawiki_api_call_helper(data, login, ...)`                | `wbi_helpers.mediawiki_api_call_helper(data, login=login, ...)`        |
| `get_wd_search_results('Douglas Adams', language='en')`      | `wbi_helpers.search_entities('Douglas Adams', language='en')`          |
| `merge_items(from_id, to_id, login_obj, ignore_conflicts='description')` | `wbi_helpers.merge_items(from_id, to_id, login=login, ignore_conflicts=['description'])` |
| `get_rdf(qid, format='turtle')`                              | `wbi_helpers.download_entity_ttl(qid)`, or `entity.download_entity_ttl()` |
| `delete_item(item, reason, login)`: a request on Wikidata:Requests for deletions | No equivalent. `wbi_helpers.delete_page()` deletes a page directly, with the delete right |
| `WDItemEngine.wikibase_item_engine_factory(mediawiki_api_url, sparql_endpoint_url)` | `wbi_config['MEDIAWIKI_API_URL']`, `wbi_config['SPARQL_ENDPOINT_URL']`, see [Installation and configuration](installation.md) |
| `WDItemEngine.setup_logging()`, `WDItemEngine.log()`         | The standard `logging` module, see [Installation and configuration](installation.md) |

WikibaseIntegrator has more helpers (redirects, lexeme forms and senses, constraint checks, value parsing,
EditGroups...): see [Helpers](helpers.md).

## Configuration

`wdi_config.config` becomes `wikibaseintegrator.wbi_config.config`, with the same keys, except:

* `USER_AGENT_DEFAULT` becomes `USER_AGENT`. Wikimedia sites require a User-Agent identifying your tool.
* `CONCEPT_BASE_URI` is gone: the concept URIs are built from `WIKIBASE_URL`.
* `MAXLAG` is gone: `maxlag` is an argument of the API calls (`mediawiki_api_call_helper(..., maxlag=5)`, 5 by
  default).
* The retries: `write()` and the API calls retry 20 times by default (`max_retries`), instead of 1000.

## Without an equivalent

These parts of WikidataIntegrator have no equivalent in WikibaseIntegrator:

* The search of an item from its data (`core_props`), see [Finding an item from its data](#finding-an-item-from-its-data).
* The good references (`good_refs`, `keep_good_ref_statements`, `KEEP_GOOD`) and the custom reference handlers
  (`ref_handler`, the `ref_handlers` module).
* `rollback()`, `get_linked_by()` (use a SPARQL query), `count_references()`, `get_reference_properties()`,
  `get_qualifier_properties()`.
* The ShEx checks (`check_entity_schema()`, `check_shex_conformance()`, `extract_shex()`).
* `wdi_helpers` (`PubmedItem`, `PublicationHelper`, `Release`, `try_write`, `prop2qid`, `id_mapper`...), `wdi_rdf`
  and `MappingRelationHelper`.
