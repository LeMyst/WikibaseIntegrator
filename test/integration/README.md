# Integration tests

The unit test suite (everything under `test/`) runs **fully offline** against a
simulated Wikibase API. The tests in this directory are different: they talk to
a **real Wikibase instance** and validate the actual end-to-end interaction
(create, read, update, delete, search, login).

They are **deselected by default** (`pytest` alone never runs them) and are
enabled with the `integration` marker plus a few environment variables.

Three files:
- `test_wikibase_roundtrip.py` writes entities with the library and reads them back: items, claims with qualifiers
  and references, and the forms and senses of a lexeme (added, edited, removed, and copied with `write(as_new=True)`).
- `test_wikibase_fastrun.py` checks the fast run mode against the query service: an item with a claim of each common
  data type, compared with the same data built locally.
- `test_wikibase_behavior.py` checks, with raw API calls, the behaviors of Wikibase that the library relies on (e.g.
  that an empty list of aliases removes the aliases of an entity). The unit tests simulate them: when one of these
  tests fails, Wikibase changed.

A known bug of the library is a strict `xfail` test (`@pytest.mark.xfail(strict=True, raises=AssertionError)`): it
passes while the bug is there, and fails once it's fixed, to be turned into a normal test.

## The docker-compose instance

`docker-compose.yml` starts:
- Wikibase, from the Wikibase Suite image `wikibase/wikibase:7` with the WikibaseLexeme extension added
  (`Dockerfile`), which the image doesn't bundle;
- the query service (`wikibase/wdqs:2`) and its updater, which loads the recent changes of the wiki every few seconds.
  The fast run tests wait for it to hold the entities they wrote.

There is no MediaInfo: the WikibaseMediaInfo extension needs WikibaseCirrusSearch, so a search backend (OpenSearch),
and uploaded files.

## In the CI

The `integration-tests.yaml` workflow starts the docker-compose instance and runs these tests: on demand
(`workflow_dispatch`), every Monday, and on the pull requests changing `test/integration/` or the workflow. It isn't a
required check of `master`, since an update of the Wikibase Suite images can break it without any change in the
library.

## Running against a local Wikibase (recommended)

```bash
docker compose -f test/integration/docker-compose.yml up -d --build
# first boot runs the MediaWiki installer; wait until http://localhost:8880 answers
```

Then set the environment variables and run the tests. The variables must be set
**in the same shell** that launches pytest (they are read when the tests are
collected); if they are missing, every integration test is silently **skipped**
and never contacts the instance.

Bash / zsh:

```bash
WBI_INTEGRATION_MEDIAWIKI_API_URL=http://localhost:8880/w/api.php \
WBI_INTEGRATION_SPARQL_ENDPOINT_URL=http://localhost:9999/bigdata/namespace/wdq/sparql \
WBI_INTEGRATION_WIKIBASE_URL=http://localhost:8880 \
WBI_INTEGRATION_USER=WikibaseAdmin \
WBI_INTEGRATION_PASSWORD=WikibaseDockerAdminPass \
pytest -m integration
```

PowerShell (Windows) — the inline `VAR=value cmd` syntax above does **not** work
here, assign `$env:` variables first:

```powershell
$env:WBI_INTEGRATION_MEDIAWIKI_API_URL = "http://localhost:8880/w/api.php"
$env:WBI_INTEGRATION_SPARQL_ENDPOINT_URL = "http://localhost:9999/bigdata/namespace/wdq/sparql"
$env:WBI_INTEGRATION_WIKIBASE_URL = "http://localhost:8880"
$env:WBI_INTEGRATION_USER = "WikibaseAdmin"
$env:WBI_INTEGRATION_PASSWORD = "WikibaseDockerAdminPass"
poetry run pytest -m integration -v -rs
```

Expect `PASSED` lines. If you see `SKIPPED ... is not set`, the variables did not
reach pytest (wrong shell syntax, or set in a different window).

The generated wiki config and the database are kept in named volumes. To reset
to a clean instance, tear it down with `docker compose -f
test/integration/docker-compose.yml down -v` (the `-v` wipes both volumes).

## Running against another instance

Any instance you are allowed to write to works (for example
[test.wikidata.org](https://test.wikidata.org) with a bot password):

| Variable | Required | Description |
| --- | --- | --- |
| `WBI_INTEGRATION_MEDIAWIKI_API_URL` | yes | URL of `api.php`. Tests are skipped when unset. |
| `WBI_INTEGRATION_USER` | for writes | Username (bot password format `User@bot` works). |
| `WBI_INTEGRATION_PASSWORD` | for writes | Password associated with the user. |
| `WBI_INTEGRATION_SPARQL_ENDPOINT_URL` | for fast run | SPARQL endpoint of the instance. The fast run tests are skipped when it or the next one is unset. |
| `WBI_INTEGRATION_WIKIBASE_URL` | for fast run | First part of the concept URIs of the instance (`http://localhost:8880` for `http://localhost:8880/entity/Q1`). |

The Lexeme tests are skipped when the instance has no WikibaseLexeme extension.

**Never point these tests at a production instance**: they create properties,
items and lexemes (and delete the items and lexemes when the user has deletion rights).
