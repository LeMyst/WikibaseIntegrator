# WikibaseIntegrator Copilot Instructions

## Repository Overview

**WikibaseIntegrator** is a Python library for programmatically reading from and writing to Wikibase instances (like Wikidata). This is a complete rewrite of WikidataIntegrator with an object-oriented architecture supporting Items, Properties, Lexemes, and MediaInfo entities.

### High-Level Details

- **Project Type**: Python library package
- **Languages**: Python 3.9+ (tested up to Python 3.14-dev)
- **Package Manager**: Poetry (pyproject.toml-based)
- **Framework**: Object-oriented design with entity-specific classes
- **Target Runtime**: Python 3.9-3.13 in production
- **Repository Size**: ~1000+ Python files across core library and tests
- **Key Features**: Two execution modes (normal and "fast run"), comprehensive data type support, OAuth authentication, SPARQL query support

### Dependencies and Build System

The project uses **Poetry** for dependency management. **Always run `python -m poetry install --with dev` before any development work** to ensure all dependencies are available in the virtual environment.

Key dependency groups:
- **Main**: backoff, mwoauth, oauthlib, requests, requests-oauthlib, ujson
- **Dev**: pytest, pylint, mypy, codespell, flynt, pylint-exit  
- **Docs**: sphinx, sphinx-rtd-theme, sphinx-autodoc-typehints, toml
- **Coverage**: pytest-cov
- **Notebooks**: jupyter, jupyterlab

## Build, Test, and Validation Commands

**CRITICAL**: All commands must be run with `python -m poetry run` prefix to use the correct virtual environment.

### Environment Setup (REQUIRED FIRST)
```bash
# Install Poetry (if not available)
python -m pip install poetry

# Install all dependencies (ALWAYS run this first)
python -m poetry install --with dev

# For documentation work, add docs dependencies
python -m poetry install --with dev,docs

# For test coverage, add coverage dependencies  
python -m poetry install --with dev,coverage
```

### Testing Commands

```bash
# Run all tests (network tests may fail in restricted environments)
python -m poetry run pytest

# Run specific test file
python -m poetry run pytest test/test_wbi_core.py

# Run tests with verbose output
python -m poetry run pytest -v

# Run tests that don't require network (safer for CI)
python -m poetry run pytest test/test_datatype_time.py test/test_wbi_exceptions.py

# Check what tests are available
python -m poetry run pytest --collect-only
```

**Test Execution Notes:**
- Some tests require network connectivity (httpbin.org, wikidata.org)
- Tests typically complete in 0.1-3 seconds for individual modules
- Network-dependent tests may timeout or fail in restricted environments
- The test suite includes 78+ tests across multiple modules

### Code Quality and Linting

**Run all linting commands in this exact order** as used in CI:

```bash
# 1. Import sorting check (fast: <1s)
python -m poetry run isort --check --diff wikibaseintegrator test

# 2. Type checking (first run installs type stubs, ~30s; subsequent ~5s)
python -m poetry run mypy --install-types --non-interactive

# 3. Code linting (slowest: ~10s, has many warnings but doesn't fail build)
python -m poetry run pylint wikibaseintegrator test || python -m poetry run pylint-exit $?

# 4. Spell checking (fast: <1s)
python -m poetry run codespell wikibaseintegrator test

# 5. String formatting check (fast: <1s)
python -m poetry run flynt -f wikibaseintegrator test
```

**Linting Notes:**
- pylint typically shows 8.79/10 rating with many warnings (mostly style-related)
- pylint uses custom configuration in pyproject.toml (max-line-length: 180)
- Use `pylint-exit` to prevent pylint warnings from failing builds
- mypy requires initial type stub installation on first run
- All linting tools are configured via pyproject.toml

### Documentation Building

```bash
# Build HTML documentation (requires --with docs dependencies)
cd docs
python -m poetry run sphinx-build -b html source build/html

# API documentation regeneration
python -m poetry run sphinx-apidoc -e -f -o docs/source ./wikibaseintegrator/ -t docs/source/_templates
```

**Documentation Notes:**
- Documentation builds in ~30s with some warnings
- Built docs available at `docs/build/html/index.html`
- ReadTheDocs integration configured via `.readthedocs.yaml`
- Uses Sphinx with RTD theme and autodoc for API reference

### Package Installation and Import Testing

```bash
# Test package imports correctly
python -m poetry run python -c "import wikibaseintegrator; print('Import successful')"

# Install package in development mode (done automatically by Poetry)
# Poetry handles this via pyproject.toml [tool.poetry.dependencies]
```

## Project Layout and Architecture

### Core Architecture

```
wikibaseintegrator/
├── __init__.py                  # Main library entry point
├── wikibaseintegrator.py        # Primary WikibaseIntegrator class
├── entities/                    # Entity-specific classes
│   ├── baseentity.py           # Base class for all entities
│   ├── item.py                 # Item entity (Q-items)
│   ├── property.py             # Property entity (P-properties) 
│   ├── lexeme.py               # Lexeme entity (L-lexemes)
│   └── mediainfo.py            # MediaInfo entity (M-mediainfo)
├── datatypes/                   # Wikibase data type implementations
│   ├── basedatatype.py         # Base data type class
│   ├── string.py, item.py, time.py, etc.  # Specific data types
│   └── extra/                  # Extended data types (edtf, localmedia)
├── models/                      # Data model classes
│   ├── claims.py               # Claims/statements management
│   ├── labels.py, descriptions.py, aliases.py  # Language values
│   └── qualifiers.py, references.py            # Claim components
├── wbi_*.py                    # Core utility modules
│   ├── wbi_config.py           # Configuration management
│   ├── wbi_login.py            # Authentication (OAuth1/2, bot passwords)
│   ├── wbi_helpers.py          # API interaction utilities
│   ├── wbi_fastrun.py          # Fast run mode implementation
│   └── wbi_enums.py            # Enumerations and constants
```

### Configuration Files

- **`pyproject.toml`** - Primary project configuration (Poetry, tools, build)
- **`.coveragerc`** - Test coverage configuration  
- **`docs/source/conf.py`** - Sphinx documentation configuration
- **`.readthedocs.yaml`** - ReadTheDocs build configuration
- **`.gitignore`** - Excludes build artifacts, `__pycache__`, `.idea/`, etc.

### GitHub Workflows and CI/CD

Located in `.github/workflows/`:

1. **`python-pytest.yaml`** - Tests on Python 3.9-3.14-dev, Ubuntu + httpbin service
2. **`python-lint.yaml`** - Code quality checks (isort, mypy, pylint, codespell, flynt) 
3. **`codeql.yml`** - Security scanning
4. **`publish-to-pypi.yaml`** - Package publishing
5. **`trivy-scan.yaml`** - Vulnerability scanning

**CI Validation Steps:**
- Tests run with httpbin service for network-dependent tests
- Poetry used for dependency management in all workflows
- Python 3.13 used for linting workflows
- Uses Ubuntu latest with pipx for Poetry installation

### Repository Files and Structure

**Root Level:**
- `README.md` - Comprehensive usage documentation and examples
- `poetry.lock` - Locked dependency versions
- `pyproject.toml` - Project configuration and dependencies
- `LICENSE` - MIT license
- `.readthedocs.yaml` - Documentation hosting configuration

**Key Directories:**
- `test/` - pytest-based test suite (78+ tests)
- `docs/` - Sphinx documentation source and build files  
- `notebooks/` - Jupyter notebook examples (6 notebooks)
- `wikibaseintegrator/` - Main library source code

### Important Implementation Notes

**Entity Architecture:**
- All entities inherit from `BaseEntity` class
- Each entity type (Item, Property, Lexeme, MediaInfo) has specialized handling
- Supports both "normal" mode (individual updates) and "fast run" mode (bulk operations)

**Data Types:**
- 20+ data type implementations (String, Item, Time, Quantity, etc.)
- Each data type inherits from `BaseDataType`
- Support for qualifiers and references on all claim types
- Special handling for Wikibase-specific types (GeoShape, TabularData, etc.)

**Authentication:**
- Supports OAuth 1.0a and 2.0, bot passwords, and username/password
- Login instances passed to WikibaseIntegrator constructor
- Required for write operations to Wikibase instances

**Network Dependencies:**
- Core functionality requires internet access for Wikibase API calls
- Some tests use httpbin.org and external services
- SPARQL functionality connects to query endpoints

## Development Guidelines

### Code Style
- Line length: 180 characters (configured in pyproject.toml)  
- Type hints required (checked by mypy)
- Docstrings expected for public methods
- F-string formatting preferred (checked by flynt)

### Common Gotchas and Workarounds

1. **Import Errors**: Always use `python -m poetry run` for all commands
2. **Network Tests**: Many tests require internet connectivity and may fail in restricted environments
3. **First mypy Run**: Takes longer due to type stub installation (`--install-types --non-interactive`)
4. **Pylint Warnings**: Many style warnings are expected, use `pylint-exit` to prevent build failures
5. **Documentation Build**: Requires `--with docs` dependency group installation

### Making Changes

1. **Always run linting before committing:**
   ```bash
   python -m poetry run isort --check --diff wikibaseintegrator test
   python -m poetry run mypy --install-types --non-interactive
   python -m poetry run pylint wikibaseintegrator test || python -m poetry run pylint-exit $?
   ```

2. **Test changes thoroughly:**
   ```bash
   python -m poetry run pytest test/
   ```

3. **For significant changes, rebuild documentation:**
   ```bash
   cd docs
   python -m poetry run sphinx-build -b html source build/html
   ```

### Validation Checklist

Before submitting changes, ensure:
- [ ] `python -m poetry install --with dev` runs successfully  
- [ ] Code imports correctly: `python -m poetry run python -c "import wikibaseintegrator"`
- [ ] Linting passes (or has acceptable warnings): all 5 linting commands
- [ ] Relevant tests pass: `python -m poetry run pytest test/test_*.py`
- [ ] No new import cycles or dependency issues introduced

## Trust These Instructions

These instructions are comprehensive and validated. Only search for additional information if:
- Commands fail with unexpected errors not covered here
- You need to understand specific business logic or entity relationships
- Working with undocumented features or advanced use cases

The build system, test framework, and validation pipeline are well-established and should work consistently when following these exact commands and procedures.