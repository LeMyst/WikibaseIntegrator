# Copilot Instructions for WikibaseIntegrator

## Project Overview

WikibaseIntegrator (WBI) is a Python library for reading from and writing to Wikibase instances (like Wikidata). It's a comprehensive toolkit that provides:

- **Entity manipulation**: Items, Properties, Lexemes, MediaInfo entities
- **Data type handling**: 15+ supported Wikibase data types (strings, quantities, time, coordinates, etc.)
- **Authentication**: OAuth 1.0a/2.0, bot passwords, username/password
- **Fast-run mode**: Efficient bulk operations with change detection
- **SPARQL integration**: Query service integration for data retrieval
- **Multi-instance support**: Works with any Wikibase instance, not just Wikidata

**Key Statistics**: ~65 Python files, ~13k lines of code, supports Python 3.9-3.14, actively maintained

## Development Environment Setup

**Prerequisites**: Python 3.9+ and Poetry package manager

### Installation Commands (ALWAYS run in order):
```bash
# 1. Install Poetry (if not already installed)
pip install poetry

# 2. Install all dependencies including dev tools
python -m poetry install --with dev

# 3. Install documentation dependencies (optional)
python -m poetry install --with docs

# 4. Install coverage tools (for testing)
python -m poetry install --with coverage
```

**Important**: Always use `python -m poetry run <command>` prefix for all development commands to ensure correct virtual environment.

## Build, Test, and Validation Workflows

### Code Quality Checks (run in this order):

1. **Import sorting**:
   ```bash
   python -m poetry run isort --check --diff wikibaseintegrator test
   ```

2. **Type checking** (requires internet on first run for type stubs):
   ```bash
   python -m poetry run mypy --install-types --non-interactive
   ```

3. **Code linting**:
   ```bash
   python -m poetry run pylint wikibaseintegrator test || python -m poetry run pylint-exit $?
   ```

4. **Spell checking**:
   ```bash
   python -m poetry run codespell wikibaseintegrator test
   ```

5. **String formatting**:
   ```bash
   python -m poetry run flynt -f wikibaseintegrator test
   ```

### Testing

**Important**: Tests require internet connectivity to connect to Wikidata. In sandboxed environments, tests may fail with connection errors - this is expected.

```bash
# Run all tests (5-10 minutes)
python -m poetry run pytest

# Run specific test file (30 seconds - 2 minutes)
python -m poetry run pytest test/test_wbi_core.py

# Run with verbose output
python -m poetry run pytest -v

# Run with coverage
python -m poetry run pytest --cov=wikibaseintegrator
```

**Timing Guidelines**:
- **Full test suite**: 5-10 minutes (network dependent)  
- **Individual test files**: 30 seconds - 2 minutes
- **Linting commands**: 10-30 seconds each
- **mypy first run**: 1-2 minutes (downloads type stubs)

### Documentation Building

```bash
# Install docs dependencies first
python -m poetry install --with docs

# Generate API documentation
sphinx-apidoc -e -f -o docs/source ./wikibaseintegrator/ -t docs/source/_templates

# Build HTML documentation
cd docs && make html
```

## Project Architecture and Layout

### Core Directory Structure:
```
wikibaseintegrator/
├── __init__.py                 # Main library entry point
├── wikibaseintegrator.py      # Main WikibaseIntegrator class
├── wbi_config.py             # Configuration settings
├── wbi_login.py              # Authentication classes
├── wbi_helpers.py            # Utility functions
├── wbi_fastrun.py           # Fast-run mode implementation
├── entities/                 # Entity classes
│   ├── baseentity.py        # Base entity class
│   ├── item.py              # Item entity
│   ├── property.py          # Property entity
│   ├── lexeme.py            # Lexeme entity
│   └── mediainfo.py         # MediaInfo entity
├── datatypes/               # Data type implementations
│   ├── basedatatype.py      # Base data type class
│   ├── string.py            # String data type
│   ├── quantity.py          # Quantity data type
│   ├── time.py              # Time data type
│   └── [13+ other types]    # Other Wikibase data types
└── models/                  # Data models
    ├── qualifiers.py        # Qualifier handling
    ├── references.py        # Reference handling
    └── [other models]
```

### Configuration Files:
- **`pyproject.toml`**: Poetry configuration, tool settings (pylint, mypy, pytest, isort)
- **`.readthedocs.yaml`**: ReadTheDocs configuration
- **`.coveragerc`**: Coverage configuration
- **`docs/source/conf.py`**: Sphinx documentation configuration

### GitHub Workflows (`.github/workflows/`):
- **`python-pytest.yaml`**: Runs tests across Python 3.9-3.14 on Ubuntu
- **`python-lint.yaml`**: Runs all code quality checks
- **`codeql.yml`**: CodeQL security analysis
- **`publish-to-pypi.yaml`**: PyPI publishing
- **`trivy-scan.yaml`**: Security vulnerability scanning

## Common Issues and Workarounds

### Network Connectivity Issues:
- Tests fail in sandboxed environments due to Wikidata API calls
- **Workaround**: Use `python -m poetry run python -c "from wikibaseintegrator import WikibaseIntegrator; print('Import successful')"` to test basic functionality

### Codespell Errors:
- Known issue: `wikibaseintegrator/datatypes/string.py:27` has typo "ine" -> should be "line"
- **Current Status**: This is an existing issue in the codebase

### mypy First Run:
- First mypy run downloads type stubs for `requests` and `ujson`
- **Always use**: `--install-types --non-interactive` flags

### Import Errors Outside Poetry:
- Direct Python import fails due to missing `ujson` dependency
- **Always use**: `python -m poetry run python` for any Python execution

## Key Dependencies and Tools:

**Runtime Dependencies**:
- `requests`, `oauthlib`, `mwoauth`: HTTP and OAuth authentication
- `ujson`: Fast JSON parsing
- `backoff`: Retry logic for API calls

**Development Tools**:
- `pytest`: Testing framework
- `pylint`: Code linting with custom configuration
- `mypy`: Static type checking
- `isort`: Import sorting
- `codespell`: Spell checking
- `flynt`: String formatting modernization

**Build Tools**:
- `poetry`: Dependency management and building
- `sphinx`: Documentation generation

## Quick Start Code Pattern:

```python
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.datatypes import ExternalID

# Configure user agent (required for Wikimedia)
config['USER_AGENT'] = 'MyBot/1.0 (https://example.com/contact)'

# Initialize client
wbi = WikibaseIntegrator()

# Get an item
item = wbi.item.get('Q42')

# Access data
label = item.labels.get('en')
```

## Validation Steps for Changes:

1. **Always run full lint suite** before committing:
   ```bash
   python -m poetry run isort --check --diff wikibaseintegrator test && \
   python -m poetry run mypy --install-types --non-interactive && \
   python -m poetry run pylint wikibaseintegrator test && \
   python -m poetry run codespell wikibaseintegrator test && \
   python -m poetry run flynt -f wikibaseintegrator test
   ```

2. **Test basic import** after code changes:
   ```bash
   python -m poetry run python -c "from wikibaseintegrator import WikibaseIntegrator"
   ```

3. **Run relevant tests** for your changes:
   ```bash
   python -m poetry run pytest test/test_relevant_module.py
   ```

## Important Notes for Agents:

- **Trust these instructions**: Only search/explore if information is incomplete or incorrect
- **Always use Poetry**: All Python commands must use `python -m poetry run` prefix
- **Network dependencies**: Be aware tests may fail in restricted environments
- **Type checking**: MyPy configuration is in `pyproject.toml`, includes custom paths
- **Line length**: Max 180 characters (configured in pyproject.toml)
- **Python versions**: Support 3.9-3.14, test matrix covers all versions
- **User agent**: Set `wbi_config['USER_AGENT']` for Wikimedia compliance

## File Locations Summary:
- **Main library**: `wikibaseintegrator/`
- **Tests**: `test/`
- **Documentation**: `docs/`
- **Examples**: `notebooks/*.ipynb`
- **Configuration**: `pyproject.toml`, `.readthedocs.yaml`
- **CI/CD**: `.github/workflows/`