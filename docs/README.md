# Documentation

The documentation is built with Sphinx and the PyData theme, and published on GitHub Pages by
`.github/workflows/docs.yaml` (`en/stable/` for the latest release, `en/latest/` for master).

The API reference is organised by topic in `source/api/`: each page lists its classes and functions with `autosummary`,
which generates one page per object in `source/api/generated/` (git-ignored) at each build. To document a new class or
function, add its name to the list of its topic page.

Build it locally:

```bash
python -m poetry install --with docs
python -m poetry run python -m sphinx -b html docs/source docs/_build/html
```
