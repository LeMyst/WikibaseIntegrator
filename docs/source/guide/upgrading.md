# Upgrading

## Breaking changes in v0.14

v0.14 changes some behaviors of v0.13 that your code may rely on:

- **The MediaWiki API calls retry by cause** (`mediawiki_api_call()` and `mediawiki_api_call_helper()`):
    - A failure (connection error, HTTP 5xx, read timeout of a read-only action) is tried at most
      `wbi_config['BACKOFF_MAX_TRIES']` times (5 by default), waiting 1, 2, 4... seconds, instead of up to 100 times
      every 60 seconds. An unreachable instance now fails after about 15 seconds instead of about 100 minutes. A read
      timeout of a write is never retried, as the edit may have been saved.
    - The instance asking to slow down (maxlag, rate limiting, HTTP 429, read-only mode) is still waited for, with the
      delay it gives, but `max_retries` defaults to 20 instead of 100. HTTP 429 used to be raised at once.
    - Once the tries are exhausted, `MaxRetriesReachedException` is raised as before, chained to the last error.
- **`backoff` is no longer a dependency**: `wbi_backoff` implements the retries of the SPARQL queries and of the logins
  itself, with the same `BACKOFF_MAX_TRIES` and `BACKOFF_MAX_VALUE` settings. Install `backoff` yourself if your own
  code imports it. `wbi_backoff()` no longer accepts the keyword arguments of `backoff.on_exception()`. Client errors
  (HTTP 4xx) other than 408 and 429 are no longer retried, and a login is tried `BACKOFF_MAX_TRIES` times in all
  (it was up to `BACKOFF_MAX_TRIES` squared CSRF token requests).
- **Some values compared through SPARQL changed**: `Property.PTYPE` is `http://wikiba.se/ontology#WikibaseProperty`
  (it was `#Property`, which never matched), and `get_sparql_value()` of `CommonsMedia`, `GeoShape` and
  `TabularData` returns the full Wikimedia Commons IRI of the value (e.g.
  `<http://commons.wikimedia.org/data/main/Data:Paris.map>` instead of `<Data:Paris.map>`).

If you want to stay on v0.13.x, you can put this line in your requirements.txt:

```
wikibaseintegrator~=0.13.0
```

## Breaking changes in v0.13

v0.13 contains changes that are not backward compatible with v0.12:

- **Python 3.11 or newer is required.** Python 3.9 and 3.10 are no longer supported.
- **The fast run mode has been rewritten** (see [Examples (in "fast run" mode)](fastrun.md)). Code
  using `wbi_fastrun` directly needs to be updated:
    - `FastRunContainer.get_items()` is renamed `get_entities()`.
    - `FastRunContainer()` takes `base_filter` as its first, mandatory argument and `base_data_type` is now optional.
      `use_refs` is renamed `use_references`, and `use_qualifiers` (default `True`), `use_rank` and `cache` are added.
    - `FastRunContainer.write_required()` drops `cqid` and gains `entity_filter` and `property_filter`.
    - `BaseEntity.write_required()` now requires `base_filter`.
    - Data types compared through SPARQL implement `from_sparql_value()`, which replaces `parse_sparql_value()` for
      the fast run mode.
- **`Form` and `Sense` compare and hash by content** (representations or glosses, grammatical features, claims)
  instead of by identity, and ignore their id. Two distinct objects holding the same content are now equal, and a
  Form/Sense modified after being added to a `set` or used as a `dict` key can no longer be found there.
- **`Claims.add()` appends by default**: its `action_if_exists` default is now `ActionIfExists.APPEND_OR_REPLACE`
  instead of `REPLACE_ALL`, like `BaseEntity.add_claims()`. Adding a claim no longer removes the existing claims with
  the same property. Pass `action_if_exists=ActionIfExists.REPLACE_ALL` to keep the previous behavior. Re-adding an
  existing value now keeps its rank and references, unless the new claim sets them.
- **HTTP requests have a default timeout** of 5 seconds to connect and 300 seconds to read. Change it with
  `wbi_config['TIMEOUT']`, or set it to `None` to wait forever as before.
- **Fewer retries by default**: `max_retries` defaults to 100 instead of 1000 in `mediawiki_api_call_helper()`.
- **`execute_sparql_query()` retries through `wbi_backoff`**: its `max_retries` parameter is ignored (with a
  `DeprecationWarning`). Failed queries are retried up to `wbi_config['BACKOFF_MAX_TRIES']` times (5 by default), with
  an exponential wait capped by `wbi_config['BACKOFF_MAX_VALUE']`, instead of up to 1000 times every 60 seconds. Once
  the retries are exhausted, the last error is raised (e.g. `requests.HTTPError`) instead of a bare `Exception`.
  Authentication errors (HTTP 401/403) are not retried.
- **Anonymous edits** that are not explicitly allowed raise `AnonymousEditNotAllowedError` instead of a bare
  `Exception`.
- **The enums mirroring API values compare equal to them**: `WikibaseDatatype`, `WikibaseRank` and `WikibaseSnakType`
  are `StrEnum`, and `WikibaseTimePrecision` is an `IntEnum`. A member is now equal to its API value
  (`WikibaseRank.PREFERRED == 'preferred'`, `WikibaseTimePrecision.DAY == 11`, both were `False`), and `str()` gives
  that value (`'preferred'` instead of `'WikibaseRank.PREFERRED'`). The JSON sent to the API is unchanged.
- **Empty values are rejected before the write**: a claim, qualifier or reference created with `None` or an empty
  string as value raises `EmptyValueError` (a `ValueError`) listing every empty value, instead of being sent and
  rejected by the API with an `MWApiError`. Use the `WikibaseSnakType.NO_VALUE` or `WikibaseSnakType.UNKNOWN_VALUE`
  snak type to state that there is no value or an unknown value.
- **`mwoauth` is no longer a dependency**: OAuth1 is implemented with `oauthlib` directly. Install `mwoauth` yourself
  if your own code imports it.
- **`wbi_helpers.default_session` and `wbi_helpers.helpers_session` are deprecated**: requests made without a login
  now use a private session per thread. The old names still work but emit a `DeprecationWarning`.

If you want to stay on v0.12.x, you can put this line in your requirements.txt:

```
wikibaseintegrator~=0.12.15
```

## Breaking changes in v0.12

A complete rewrite of the WikibaseIntegrator core has been done in v0.12 which has led to some important changes.

It offers a new object-oriented approach, better code readability and support for Property, Lexeme and MediaInfo
entities (in addition to Item).

If you want to stay on v0.11.x, you can put this line in your requirements.txt:

```
wikibaseintegrator~=0.11.3
```
