# WikibaseIntegrator — Agent Guide

Python library for reading from and writing to Wikibase instances (Wikidata and others). Supports Items, Properties, Lexemes, and MediaInfo entities with full OAuth authentication, SPARQL queries, and a fast-run bulk-write mode.

## Development setup

Uses [Poetry](https://python-poetry.org/) for dependency management.

```bash
poetry install --with dev          # core + dev tools
poetry install --with dev,coverage # add coverage reporting
poetry install --with docs         # add Sphinx doc dependencies
```

Python 3.11–3.15 supported. CI tests all versions; lint runs on 3.14.

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
poetry run isort --check --diff wikibaseintegrator test scripts
poetry run mypy --install-types --non-interactive
poetry run pylint --fail-under=0 --fail-on=E,W,F wikibaseintegrator scripts
poetry run pylint --fail-under=0 --fail-on=E,W,F --disable=redefined-outer-name,unused-argument,protected-access test
poetry run codespell wikibaseintegrator test scripts
poetry run flynt -f wikibaseintegrator test scripts
```

The same checks are available as [pre-commit](https://pre-commit.com/) hooks ([.pre-commit-config.yaml](.pre-commit-config.yaml)): isort/flynt/codespell on commit, mypy/pylint on push. They are `local` hooks that run the Poetry-installed tools (so versions follow `poetry.lock`), which requires the project virtualenv to be active. Run them all with `pre-commit run --all-files --hook-stage pre-push`.

Key style rules (from [pyproject.toml](pyproject.toml)):
- Max line length: **179/180** characters (isort/pylint)
- isort profile: `black` with `force_sort_within_sections = true`
- mypy: `ignore_missing_imports = true`, `warn_unused_ignores = true`, and `disallow_untyped_defs` for the package (it ships `py.typed`): every function of `wikibaseintegrator/` must be annotated; the tests are exempt
- Pylint: errors and warnings fail CI, conventions and refactoring suggestions are only reported. `fixme`, `invalid-name`, `too-few-public-methods`, `too-many-arguments`, and several other checks are disabled — check the `[tool.pylint]` section before suppressing new warnings, and prefer a scoped `# pylint: disable-next=<check>` with a reason over a broad disable

## Project layout

```
wikibaseintegrator/
├── wikibaseintegrator.py   # Main WikibaseIntegrator class (entry point)
├── wbi_login.py            # OAuth2 / OAuth1 / bot-password / clientlogin auth
├── wbi_helpers.py          # Utility functions (search, merge, SPARQL, etc.)
├── wbi_config.py           # Global config (mediawiki_api_url, etc.)
├── wbi_fastrun.py          # Fast-run mode for bulk writes
├── wbi_backoff.py          # Retry/backoff decorator
├── wbi_editgroups.py       # EditGroups batch links for edit summaries
├── wbi_enums.py            # Enumerations shared across modules
├── wbi_exceptions.py       # Custom exception hierarchy
├── py.typed                # PEP 561 marker — keep it (ships type hints)
├── datatypes/              # One file per Wikibase data type (18 types)
│   └── extra/              # Optional extensions (EDTF, LocalMedia)
├── entities/               # Item, Property, Lexeme, MediaInfo, BaseEntity
└── models/                 # Claims, Qualifiers, References, Labels, etc.
test/                       # pytest test files (mirrors wikibaseintegrator/ loosely)
docs/                       # Sphinx source
scripts/                    # Maintenance scripts (test fixture refresh)
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
| `python-pytest.yaml` | push/PR to master | Matrix test on Python 3.11–3.15 |
| `python-lint.yaml` | push/PR to master | isort, mypy, pylint, codespell, flynt |
| `docs.yaml` | push/PR to master, release published, manual | Build the Sphinx documentation (warnings as errors) and publish it on GitHub Pages: `en/latest/` from master, `en/stable/` from the latest release, stored in the `gh-pages` branch |
| `update-test-fixtures.yaml` | monthly / manual | Refresh `test/fixtures/` from live APIs (`scripts/update_test_fixtures.py`), open a PR if changed |
| `codeql.yml` | push/PR/schedule | Static security analysis |
| `trivy-scan.yaml` | push/PR/schedule | Vulnerability scanning |
| `publish-to-pypi.yaml` | GitHub release published / push / PR | Build the package; on a published release, publish it to TestPyPI and PyPI and attach the signed files to the release |
| `auto-assign-issue.yaml` | issue opened | Auto-assign new issues to the maintainer |

## Releasing

Publishing a GitHub release publishes the package. Pushing a tag by hand doesn't.

1. Label the PRs merged since the previous release. `.github/release.yml` groups the generated release notes by label: `breaking change` (matching the README "Breaking changes" section), `enhancement`, `bug`, `documentation`, `dependencies`. Unlabelled PRs go to "Other changes".
2. Merge a PR setting the release version in `pyproject.toml` (e.g. `0.13.0`, dropping `.dev0`) and the tag of the README install example.
3. On GitHub, draft a new release: create the tag `vX.Y.Z` on `master`, click "Generate release notes", review them, then publish. The `publish-to-pypi.yaml` workflow checks that the tag matches the version of `pyproject.toml`, publishes to TestPyPI then PyPI, and attaches the Sigstore-signed files to the release.
4. Merge a PR bumping `pyproject.toml` to the next `.dev0` version (e.g. `0.13.1.dev0`).

Publishing to PyPI can't be undone: leave step 3 to the maintainer.

## Notes for agents

- The virtual environment is at `.venv/`; Poetry manages it automatically.
- Work in a dedicated git worktree under `.claude/worktrees/` (git-ignored; e.g. `git worktree add .claude/worktrees/<topic> -b <topic> master`) rather than switching branches in the main checkout, so the user's working copy is never disturbed. Each worktree needs its own environment (`poetry install --with dev`).
- `wbi_config.py` holds the default `mediawiki_api_url` (`https://www.wikidata.org/w/api.php`). Unit tests must never hit a real API: use the `wikibase` fixture (MockWikibase) or `requests_mock` directly; real-instance scenarios belong in `test/integration/`.
- The `fastrun` module caches entity data before bulk writes to avoid redundant API calls — changes there require careful testing to avoid stale cache issues.
- `datatypes/extra/` contains optional extensions with their own dependencies; do not import them unconditionally from core modules.
- Version string is in `pyproject.toml` (`version`: the release, e.g. `0.13.0`, or a `.dev0` version between releases); `wikibaseintegrator/__init__.py` exposes it as `__version__` by reading the installed package metadata (`importlib.metadata`), so there is nothing to update there.
