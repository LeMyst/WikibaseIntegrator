# WikibaseIntegrator Copilot Instructions

The instructions for coding agents are in [AGENTS.md](../AGENTS.md), at the root of the repository: development setup,
tests, lint commands (the same as the CI), project layout, conventions and the release process. Read it before any
change; it is kept up to date, this file only points to it.

The essentials:

- Python 3.11 to 3.15, dependencies managed with Poetry: `poetry install --with dev`.
- The unit tests run fully offline (`poetry run pytest`): the HTTP calls are served by the simulated Wikibase of
  `test/conftest.py`. A unit test must never reach a real instance; those belong to `test/integration/`, deselected by
  default.
- Run the lint checks of AGENTS.md (isort, mypy, pylint, codespell, flynt) before proposing a change: pylint errors and
  warnings fail the CI, and every function of the package must be annotated.
- The user documentation is in `docs/source/guide/` (Markdown), the API reference in `docs/source/api/`.
