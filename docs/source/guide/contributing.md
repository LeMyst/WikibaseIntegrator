# Contributing

## Installation of the development environment

The following commands will install the development environment with the necessary dependencies:

```bash
python -m poetry install --with dev,coverage
```

The `docs` and `notebooks` groups are also available (`--with docs,notebooks`) to build the documentation and run the
Jupyter notebooks.

The unit tests run offline (the HTTP calls are mocked) with:

```bash
python -m pytest
```

Add `--cov=wikibaseintegrator` to measure the test coverage (requires the `coverage` group), as the CI does on Python
3.14 for the coverage badge.

The integration tests, running against a real Wikibase instance, are deselected by default and can be run with
`python -m pytest -m integration` (see [test/integration/README.md](https://github.com/LeMyst/WikibaseIntegrator/blob/master/test/integration/README.md)).

Optionally, [pre-commit](https://pre-commit.com/) can run the lint checks of the CI before each commit (isort, flynt,
codespell) and before each push (mypy, pylint), using the tools installed by Poetry:

```bash
pipx install pre-commit  # or use "uvx pre-commit"
pre-commit install
```
