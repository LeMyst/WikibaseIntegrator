"""Tests for Reference.from_json() handling of optional fields."""

import pytest
from wikibaseintegrator.models.references import Reference, References


def test_reference_from_json_without_hash():
    """Test that Reference.from_json() works without hash field (new references)."""
    json_data = {
        'snaks': {},
        'snaks-order': []
    }
    reference = Reference().from_json(json_data)
    
    assert reference.hash is None
    assert len(reference.snaks) == 0
    assert reference.snaks_order == []


def test_reference_from_json_with_hash():
    """Test that Reference.from_json() works with hash field (Wikidata format)."""
    json_data = {
        'hash': 'abc123def456',
        'snaks': {},
        'snaks-order': []
    }
    reference = Reference().from_json(json_data)
    
    assert reference.hash == 'abc123def456'
    assert len(reference.snaks) == 0
    assert reference.snaks_order == []


def test_references_from_json_without_hash():
    """Test that References.from_json() works with list of references without hash."""
    json_data = [
        {'snaks': {}, 'snaks-order': []},
        {'snaks': {}, 'snaks-order': []}
    ]
    references = References().from_json(json_data)
    
    assert len(references) == 2
    # Iterate to access individual references
    ref_list = list(references.references)
    assert ref_list[0].hash is None
    assert ref_list[1].hash is None


def test_references_from_json_with_hash():
    """Test that References.from_json() works with list of references with hash."""
    json_data = [
        {'hash': 'hash1', 'snaks': {}, 'snaks-order': []},
        {'hash': 'hash2', 'snaks': {}, 'snaks-order': []}
    ]
    references = References().from_json(json_data)
    
    assert len(references) == 2
    ref_list = list(references.references)
    assert ref_list[0].hash == 'hash1'
    assert ref_list[1].hash == 'hash2'


def test_reference_from_json_mixed_hash():
    """Test that References.from_json() handles mix of with/without hash."""
    json_data = [
        {'hash': 'hash1', 'snaks': {}, 'snaks-order': []},
        {'snaks': {}, 'snaks-order': []},
        {'hash': 'hash3', 'snaks': {}, 'snaks-order': []}
    ]
    references = References().from_json(json_data)
    
    assert len(references) == 3
    ref_list = list(references.references)
    assert ref_list[0].hash == 'hash1'
    assert ref_list[1].hash is None
    assert ref_list[2].hash == 'hash3'
