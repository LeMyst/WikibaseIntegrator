# Integration tests

The unit test suite (everything under `test/`) runs **fully offline** against a
simulated Wikibase API. The tests in this directory are different: they talk to
a **real Wikibase instance** and validate the actual end-to-end interaction
(create, read, update, delete, search, login).

They are **deselected by default** (`pytest` alone never runs them) and are
enabled with the `integration` marker plus a few environment variables.

## Running against a local Wikibase (recommended)

```bash
docker compose -f test/integration/docker-compose.yml up -d
# first boot runs the MediaWiki installer; wait until http://localhost:8880 answers
```

Then set the environment variables and run the tests. The variables must be set
**in the same shell** that launches pytest (they are read when the tests are
collected); if they are missing, every integration test is silently **skipped**
and never contacts the instance.

Bash / zsh:

```bash
WBI_INTEGRATION_MEDIAWIKI_API_URL=http://localhost:8880/w/api.php \
WBI_INTEGRATION_USER=WikibaseAdmin \
WBI_INTEGRATION_PASSWORD=WikibaseDockerAdminPass \
pytest -m integration
```

PowerShell (Windows) — the inline `VAR=value cmd` syntax above does **not** work
here, assign `$env:` variables first:

```powershell
$env:WBI_INTEGRATION_MEDIAWIKI_API_URL = "http://localhost:8880/w/api.php"
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
| `WBI_INTEGRATION_SPARQL_ENDPOINT_URL` | no | SPARQL endpoint, if the instance has one. |

**Never point these tests at a production instance**: they create properties
and items (and delete the items when the user has deletion rights).
