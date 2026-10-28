import ast
import importlib
from pathlib import Path

import pytest

from wikibaseintegrator import models
from wikibaseintegrator.models.form import Form
from wikibaseintegrator.models.reference import Reference
from wikibaseintegrator.models.representations import Representations
from wikibaseintegrator.models.sitelink import Sitelink
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks

MODELS_DIR = Path(models.__file__).parent

# Every model class, with the module that defines it
CLASSES = {
    'Alias': 'alias',
    'Aliases': 'aliases',
    'BaseModel': 'basemodel',
    'Claim': 'claim',
    'Claims': 'claims',
    'Descriptions': 'descriptions',
    'Form': 'form',
    'Forms': 'forms',
    'Glosses': 'glosses',
    'Labels': 'labels',
    'LanguageValue': 'language_value',
    'LanguageValues': 'language_values',
    'Lemmas': 'lemmas',
    'Qualifiers': 'qualifiers',
    'Reference': 'reference',
    'References': 'references',
    'Representations': 'representations',
    'Sense': 'sense',
    'Senses': 'senses',
    'Sitelink': 'sitelink',
    'Sitelinks': 'sitelinks',
    'Snak': 'snak',
    'Snaks': 'snaks',
}

# Classes that moved to their own module, with the module they used to be defined in
LEGACY_LOCATIONS = {
    'Alias': 'aliases',
    'Claim': 'claims',
    'Form': 'forms',
    'Glosses': 'senses',
    'LanguageValue': 'language_values',
    'Reference': 'references',
    'Representations': 'forms',
    'Sense': 'senses',
    'Sitelink': 'sitelinks',
    'Snak': 'snaks',
}


def _top_level_model_imports(path: Path) -> set[str]:
    # Imports done at module level, ignoring the ones inside functions or behind `if TYPE_CHECKING:`
    imported = set()
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 1:
                imported.add(node.module)
            elif node.module.startswith('wikibaseintegrator.models.'):
                imported.add(node.module.removeprefix('wikibaseintegrator.models.'))
    return imported


def test_one_class_per_module():
    for path in MODELS_DIR.glob('*.py'):
        if path.name == '__init__.py':
            continue
        classes = [node.name for node in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1, f'{path.name} defines {classes}'


@pytest.mark.parametrize('name, module', CLASSES.items())
def test_class_defined_in_own_module(name, module):
    cls = getattr(importlib.import_module(f'wikibaseintegrator.models.{module}'), name)
    assert cls.__module__ == f'wikibaseintegrator.models.{module}'
    assert getattr(models, name) is cls


@pytest.mark.parametrize('name, legacy_module', LEGACY_LOCATIONS.items())
def test_legacy_import_location(name, legacy_module):
    # The classes used to share a module with their container class, keep these imports working
    legacy = getattr(importlib.import_module(f'wikibaseintegrator.models.{legacy_module}'), name)
    assert legacy is getattr(importlib.import_module(f'wikibaseintegrator.models.{CLASSES[name]}'), name)


def test_no_circular_import_at_module_level():
    graph = {path.stem: _top_level_model_imports(path) for path in MODELS_DIR.glob('*.py') if path.name != '__init__.py'}

    visiting: list[str] = []
    done: set[str] = set()

    def visit(module: str) -> None:
        assert module not in visiting, f"circular import: {' -> '.join(visiting[visiting.index(module):] + [module])}"
        if module in done:
            return
        visiting.append(module)
        for dependency in graph.get(module, set()):
            visit(dependency)
        visiting.pop()
        done.add(module)

    for module in graph:
        visit(module)


def test_form_default_representations():
    assert isinstance(Form().representations, Representations)


def test_snaks_compare_with_other_types():
    assert Snaks() == Snaks()
    assert Snaks() != 'P31'
    assert Snaks() != None  # noqa: E711  # pylint: disable=singleton-comparison


def test_sitelink_str_without_title():
    assert str(Sitelink(site='enwiki')) == ''
    assert str(Sitelink(site='enwiki', title='Douglas Adams')) == 'Douglas Adams'


def test_reference_add_none():
    reference = Reference()
    reference.add(None)
    assert len(reference) == 0

    reference.add(Snak(property_number='P828', datavalue={'value': 'string', 'type': 'string'}, datatype='string'))
    assert len(reference) == 1
