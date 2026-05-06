# Local Wikibase CI

This directory contains the first rollout of local Wikibase integration testing for `WikibaseIntegrator`.

## What it does

- Starts a local Wikibase container for CI jobs.
- Waits until the MediaWiki API is reachable.
- Seeds minimal deterministic test entities.
- Runs a subset of integration tests against the local endpoint instead of public Wikidata.

## Files

- `docker-compose.yml`: local service definition used by GitHub Actions.
- `wait_for_api.py`: polling script for API readiness.
- `seed_local_wikibase.py`: creates initial test properties, one item, and one lexeme.

## Expected environment variables

- `WBI_MEDIAWIKI_API_URL` (default: `http://127.0.0.1:8181/w/api.php`)
- `WBI_WIKIBASE_URL` (default: `http://127.0.0.1:8181`)
- `WBI_TEST_USERNAME` (default: `Admin`)
- `WBI_TEST_PASSWORD` (default: `adminpass`)

## Notes

- MediaInfo tests still require Wikimedia Commons and are tagged with `requires_commons`.
- SPARQL-heavy tests are tagged with `requires_sparql` and currently excluded from this local lane.
- If the Wikibase container image changes upstream, adjust `docker-compose.yml` accordingly.

