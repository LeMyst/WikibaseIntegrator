# Upgrading

The breaking changes of each release, and the code to change. The [versioning and deprecation policy](versioning.md)
says what can change in which release.

## Breaking changes in v0.15

v0.15 is the last release before 1.0, which freezes the public API under semantic versioning. It gathers the
changes of the API and of the behavior that have to happen before the freeze. Where a transition is possible, the
old behavior is kept in v0.15 with a `DeprecationWarning` and removed in 1.0.

- **`Qualifiers.set()` replaces the qualifiers** given as a list or a `Qualifiers` object, like it already did with
  a dict or `None`. It used to add them to the existing qualifiers: call `add()` for each qualifier to keep that.
- **The `references` of a claim reject the items they can't use**: an item of the list that is neither a `Claim`, a
  list of `Claim` nor a `Reference` raises a `ValueError`. It used to add an empty reference.
- **An empty value removes a label, a description or a lemma**: `labels.set('en', '')` marks the existing label
  for removal, like `labels.set('en', None)` and like Wikibase does with an empty value, and returns `None`. It used
  to leave the label unchanged.
- **A `Quantity` takes both bounds or none**: a single `upper_bound` or `lower_bound` raises a `ValueError`. Wikibase
  rejects such a quantity when it is written, so it used to fail later, at the write.
- **`write(as_new=True)` only sends what belongs to the new entity**: the GUIDs of the claims, the ids of the forms
  and senses of a lexeme, and the claims, terms, forms and senses marked for removal are left out. They used to be
  sent along with the copy, with the GUIDs of the entity it was read from.
- **A request with a login and `allow_anonymous=True` uses the edit token of the login**: the request is made with
  the session of the login, which rejects the anonymous token. It used to send the anonymous token, so such an edit
  failed with a `badtoken` error. A `token` given in the data is still sent as it is.
- **Invalid arguments raise `TypeError` or `ValueError` instead of `AssertionError`**: a value of the wrong type
  given to a data type (e.g. `String(value=1)`), to the models (`Qualifiers`, `Reference`, `References`,
  `LanguageValues`, `Claim.qualifiers`) or to `generate_entity_instances()` raises a `TypeError`, and an
  `action_if_exists` that `Aliases.set()` or `LanguageValues.set()` doesn't support raises a `ValueError`. These
  checks were `assert` statements, which `python -O` skips. Catch `TypeError` or `ValueError` instead of
  `AssertionError`.
- **Fast run matches the BCE dates and the dates of the Julian calendar**, and compares the calendar model of the
  dates. `Time.sparql_time()` gives the timestamp of the RDF export of Wikibase: from the year precision, the BCE
  years are numbered like in XSD 1.1 (`-0044` is `-0043`), and from the day precision, a date of the Julian calendar
  is converted to the Gregorian calendar. `Time.from_sparql_value()` reads the timestamp back as a date of the
  Gregorian calendar, the calendar of `xsd:dateTime` (`-0043-03-15T00:00:00Z` is `-0044-03-15T00:00:00Z`), and the
  new `Time.time_from_sparql()` reads it knowing its precision and calendar model. Fast run used to report a write as
  required for these dates, and to match a date with the same timestamp in another calendar.
- **`action_if_exists` is applied by `Qualifiers.add()`, `Reference.add()`, `References.add()` and `Senses.add()`**,
  which ignored it, and by `Forms.add()`, which gets the parameter. It has the semantics of `Claims.add()`:
  - With the default `APPEND_OR_REPLACE`, adding a qualifier, a snak of a reference or a reference that is already
    there does nothing, and so does adding a form or a sense with the same content as one of the lexeme. These used to
    always be appended, except by `References.add()`, which already skipped an equal reference.
  - A form or a sense with the id of one of the lexeme replaces it.
  - `KEEP` only adds when there is nothing yet: no qualifier or snak of the property, no reference, no form or sense.
  - `REPLACE_ALL` removes the others. The forms and the senses are marked for removal, like the claims.

  Pass `ActionIfExists.FORCE_APPEND` to add duplicates. `Qualifiers.set()` and the `from_json()` methods keep every
  item they are given.
- **`Aliases.set()` refuses `FORCE_APPEND` and `MERGE_REFS_OR_APPEND`** with a `ValueError`: a duplicate alias is
  dropped by Wikibase and aliases have no references, and these actions used to do nothing at all, silently.
- **`len()` counts the elements of every collection**, like the iteration: the claims of `Claims`, the qualifiers of
  `Qualifiers`, the snaks of `Snaks` and of a `Reference`, the aliases of `Aliases`. It used to count their distinct
  properties, or languages for `Aliases`: `len(item.claims)` was the number of properties with a claim. Count them
  with `len({claim.mainsnak.property_number for claim in item.claims})` if you need it. The elements marked for
  removal are counted, like the iteration gives them.
  - Every collection has a `count()`, the same as `len()`. `Claims.count()` and `Qualifiers.count()` already counted
    the elements.
  - `Aliases` is iterable over its aliases, of every language.

### Deprecated in v0.15, removed in 1.0

These APIs still work in v0.15 and emit a `DeprecationWarning`. They will be removed in 1.0:

- **`parse_sparql_value()`** of the data types: use `from_sparql_value()`, which takes the JSON binding of the value
  returned by the SPARQL query (e.g. `{'type': 'literal', 'value': 'Paris'}`) instead of its string form.
- **`wbi_helpers.BColors`**: the library no longer emits ANSI color codes. Copy the codes into your own code if you
  use them.
- **`wbi_helpers.default_session` and `wbi_helpers.helpers_session`** (deprecated since v0.13): the session of the
  requests made without a login is per-thread and private.
- **The `max_retries` parameter of `execute_sparql_query()`** (deprecated and ignored since v0.13): the retries of
  the SPARQL queries are set by `wbi_config['BACKOFF_MAX_TRIES']`.
- **Importing `Representations` from `wikibaseintegrator.models.forms` and `Glosses` from
  `wikibaseintegrator.models.senses`**: import them from `wikibaseintegrator.models`.
- **`in` on a `Claim`** (`x in claim`): a claim isn't a collection. Compare the claims with `==`, and read the
  value of a claim from `claim.mainsnak.datavalue`. With a string, it never matched anything. `'P31' in item.claims`
  isn't concerned.

If you want to stay on v0.14.x, you can put this line in your requirements.txt:

```
wikibaseintegrator~=0.14.0
```

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
