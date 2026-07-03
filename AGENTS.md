# WikibaseIntegrator — Agent Guide

Python library for reading from and writing to Wikibase instances (Wikidata and others). Supports Items, Properties, Lexemes, and MediaInfo entities with full OAuth authentication, SPARQL queries, and a fast-run bulk-write mode.

## Development setup

Uses [Poetry](https://python-poetry.org/) for dependency management.

```bash
poetry install --with dev          # core + dev tools
poetry install --with dev,coverage # add coverage reporting
poetry install --with docs         # add Sphinx doc dependencies
```

Python 3.10–3.15 supported. CI tests all versions; lint runs on 3.14.

## Running tests

```bash
poetry run pytest
```

Tests live in `test/` and run **fully offline**: all HTTP traffic is intercepted by `requests-mock` and served by the `MockWikibase` emulation defined in [test/conftest.py](test/conftest.py), backed by the JSON fixtures in `test/fixtures/`. Coverage is configured in [.coveragerc](.coveragerc) (branch coverage enabled).

Integration tests against a real Wikibase instance live in `test/integration/` and are deselected by default; see [test/integration/README.md](test/integration/README.md) (`pytest -m integration` + `WBI_INTEGRATION_*` environment variables, docker-compose file provided).

The fixtures are pruned copies of real entities (Q582, P50, L5, M75908279). Refresh them with `python scripts/update_test_fixtures.py` — the script fetches live data, prunes it to what the tests use, normalizes volatile fields and validates the invariants the tests rely on. A monthly workflow (`update-test-fixtures.yaml`) does this automatically and opens a PR when needed.

## Code quality

Run all checks in the same order as CI:

```bash
poetry run isort --check --diff wikibaseintegrator test
poetry run mypy --install-types --non-interactive
poetry run pylint wikibaseintegrator test
poetry run codespell wikibaseintegrator test
poetry run flynt -f wikibaseintegrator test
```

Key style rules (from [pyproject.toml](pyproject.toml)):
- Max line length: **179/180** characters (isort/pylint)
- isort profile: `black` with `force_sort_within_sections = true`
- mypy: `ignore_missing_imports = true`; type annotations are expected throughout
- Pylint: `fixme`, `invalid-name`, `too-few-public-methods`, `too-many-arguments`, and several other checks are disabled — check the `[tool.pylint]` section before suppressing new warnings

## Project layout

```
wikibaseintegrator/
├── wikibaseintegrator.py   # Main WikibaseIntegrator class (entry point)
├── wbi_login.py            # OAuth2 / OAuth1 / bot-password auth
├── wbi_helpers.py          # Utility functions (search, merge, SPARQL, etc.)
├── wbi_config.py           # Global config (mediawiki_api_url, etc.)
├── wbi_fastrun.py          # Fast-run mode for bulk writes
├── wbi_backoff.py          # Retry/backoff decorator
├── wbi_enums.py            # Enumerations shared across modules
├── wbi_exceptions.py       # Custom exception hierarchy
├── datatypes/              # One file per Wikibase data type (22 types)
│   └── extra/              # Optional extensions (EDTF, LocalMedia)
├── entities/               # Item, Property, Lexeme, MediaInfo, BaseEntity
└── models/                 # Claims, Qualifiers, References, Labels, etc.
test/                       # pytest test files (mirrors wikibaseintegrator/ loosely)
docs/                       # Sphinx source
notebooks/                  # Jupyter usage examples
```

## Key conventions

- **Type hints everywhere** — mypy is enforced in CI; add annotations to all new public signatures.
- **No bare `except`** — catch specific exceptions; raise `wbi_exceptions` types at API boundaries.
- **Datatype pattern** — each new data type subclasses `BaseDataType` (`datatypes/basedatatype.py`); follow the existing pattern for `__init__`, `from_json`, and `get_json`.
- **Entity pattern** — entity classes subclass `BaseEntity` (`entities/baseentity.py`).
- **No breaking changes to public API** without a version bump and changelog entry.
- **Imports** — keep sorted with isort; standard library → third-party → local, all alphabetical within sections.
- **String formatting** — flynt enforces f-strings; do not use `.format()` or `%` style.

## CI workflows (`.github/workflows/`)

| Workflow | Trigger | What it does |
|---|---|---|
| `python-pytest.yaml` | push/PR to master | Matrix test on Python 3.10–3.15 |
| `python-lint.yaml` | push/PR to master | isort, mypy, pylint, codespell, flynt |
| `update-test-fixtures.yaml` | monthly / manual | Refresh `test/fixtures/` from live APIs (`scripts/update_test_fixtures.py`), open a PR if changed |
| `codeql.yml` | push/PR/schedule | Static security analysis |
| `trivy-scan.yaml` | push/PR/schedule | Vulnerability scanning |
| `publish-to-pypi.yaml` | GitHub release | Publish to PyPI |

## Notes for agents

- The virtual environment is at `.venv/`; Poetry manages it automatically.
- `wbi_config.py` holds the default `mediawiki_api_url` (`https://www.wikidata.org/w/api.php`). Unit tests must never hit a real API: use the `wikibase` fixture (MockWikibase) or `requests_mock` directly; real-instance scenarios belong in `test/integration/`.
- The `fastrun` module caches entity data before bulk writes to avoid redundant API calls — changes there require careful testing to avoid stale cache issues.
- `datatypes/extra/` contains optional extensions with their own dependencies; do not import them unconditionally from core modules.
- Version string is in `pyproject.toml` (`version = "0.12.16.dev0"`) and mirrored in `wikibaseintegrator/__init__.py`.
