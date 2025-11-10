"""
Test to demonstrate the claims.add() bug where adding a claim deletes other claims with the same property.
"""
import pytest

from wikibaseintegrator.datatypes import Item, MonolingualText
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.wbi_enums import ActionIfExists


def test_claims_add_should_not_replace_by_default():
    """
    Test that claims.add() without action_if_exists parameter should append, not replace.
    This tests the expected behavior described in the issue.
    Default behavior should be APPEND_OR_REPLACE.
    """
    claims = Claims()
    
    # Add first claim with property P1476 (title)
    claim1 = MonolingualText(text='German Title', language='de', prop_nr='P1476')
    claims.add(claim1)
    
    # Add second claim with same property
    claim2 = MonolingualText(text='French Title', language='fr', prop_nr='P1476')
    claims.add(claim2)
    
    # Both claims should exist (different values, so both added)
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 2, f"Expected 2 claims but got {len(p1476_claims)}"
    assert all(not c.removed for c in p1476_claims), "No claims should be marked as removed"
    
    # Add third claim with same property - this should also append
    claim3 = MonolingualText(text='English Title', language='en', prop_nr='P1476')
    claims.add(claim3)
    
    # All three claims should exist
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 3, f"Expected 3 claims but got {len(p1476_claims)}"
    assert all(not c.removed for c in p1476_claims), "No claims should be marked as removed"
    
    # Try adding duplicate - should not add again (APPEND_OR_REPLACE behavior)
    claim4 = MonolingualText(text='English Title', language='en', prop_nr='P1476')
    claims.add(claim4)
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 3, f"Expected 3 claims (no duplicate) but got {len(p1476_claims)}"


def test_claims_add_explicit_append_or_replace():
    """
    Test that claims.add() with ActionIfExists.APPEND_OR_REPLACE appends new claims.
    """
    claims = Claims()
    
    # Add first claim
    claim1 = MonolingualText(text='German Title', language='de', prop_nr='P1476')
    claims.add(claim1, action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
    
    # Add second claim with same property
    claim2 = MonolingualText(text='French Title', language='fr', prop_nr='P1476')
    claims.add(claim2, action_if_exists=ActionIfExists.APPEND_OR_REPLACE)
    
    # Both claims should exist
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 2, f"Expected 2 claims but got {len(p1476_claims)}"


def test_claims_add_explicit_replace_all():
    """
    Test that claims.add() with ActionIfExists.REPLACE_ALL marks old claims as removed.
    """
    claims = Claims()
    
    # Add first claim
    claim1 = MonolingualText(text='German Title', language='de', prop_nr='P1476')
    claims.add(claim1, action_if_exists=ActionIfExists.REPLACE_ALL)
    
    # Add second claim with same property - this should mark first claim as removed
    claim2 = MonolingualText(text='French Title', language='fr', prop_nr='P1476')
    claims.add(claim2, action_if_exists=ActionIfExists.REPLACE_ALL)
    
    # Both claims are in the list, but first one should be marked as removed
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 2, f"Expected 2 claims in list but got {len(p1476_claims)}"
    assert p1476_claims[0].removed is True, "First claim should be marked as removed"
    assert p1476_claims[1].removed is False, "Second claim should not be marked as removed"
    assert p1476_claims[1].mainsnak.datavalue['value']['text'] == 'French Title'


def test_claims_add_replace_all_with_existing_id():
    """
    Test that claims.add() with ActionIfExists.REPLACE_ALL marks existing claims with ID as removed.
    This simulates what happens when claims are fetched from the server.
    """
    claims = Claims()
    
    # Add first claim and simulate it having been fetched from server (has an id)
    claim1 = MonolingualText(text='German Title', language='de', prop_nr='P1476')
    claim1.id = 'Q123$ABC-DEF-GHI'  # Simulate server-assigned ID
    claims.add(claim1, action_if_exists=ActionIfExists.FORCE_APPEND)
    
    # Add second claim with same property using EXPLICIT REPLACE_ALL (not default)
    claim2 = MonolingualText(text='English Title', language='en', prop_nr='P1476')
    claims.add(claim2, action_if_exists=ActionIfExists.REPLACE_ALL)  # Explicit REPLACE_ALL
    
    # Both claims are in the list
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 2
    
    # First claim should be marked as removed (because we used REPLACE_ALL)
    assert p1476_claims[0].removed is True
    assert p1476_claims[0].id == 'Q123$ABC-DEF-GHI'
    
    # Second claim should not be removed
    assert p1476_claims[1].removed is False
    
    # When serialized to JSON, the removed claim with ID should have 'remove' field
    json_data = claims.get_json()
    assert 'P1476' in json_data
    assert len(json_data['P1476']) == 2  # Both claims in JSON because first has ID
    
    # Find the claim with 'remove' field
    removed_claims = [c for c in json_data['P1476'] if 'remove' in c]
    assert len(removed_claims) == 1, "Should have one claim marked for removal"
    
    # The other claim should be the new one
    active_claims = [c for c in json_data['P1476'] if 'remove' not in c]
    assert len(active_claims) == 1
    assert active_claims[0]['mainsnak']['datavalue']['value']['text'] == 'English Title'


def test_claims_add_different_properties():
    """
    Test that claims.add() doesn't affect claims with different properties.
    """
    claims = Claims()
    
    # Add claim with property P31 (instance of)
    claim1 = Item(value='Q5', prop_nr='P31')
    claims.add(claim1)
    
    # Add claim with property P1476 (title)
    claim2 = MonolingualText(text='English Title', language='en', prop_nr='P1476')
    claims.add(claim2)
    
    # Both claims should exist
    assert len(claims.get('P31')) == 1
    assert len(claims.get('P1476')) == 1


def test_issue_scenario_adding_claim_preserves_existing():
    """
    Test the exact scenario from the GitHub issue:
    - Entity has existing claims with same property (with IDs from server)
    - User adds a new claim with same property
    - Existing claims should be preserved, not deleted
    """
    claims = Claims()
    
    # Simulate existing claims fetched from server (have IDs)
    claim1 = MonolingualText(text='Flametti oder vom Dandysmus der Armen', language='de', prop_nr='P1476')  # codespell:ignore oder
    claim1.id = 'Q105624761$1234-5678-90AB'
    claims.add(claim1, action_if_exists=ActionIfExists.FORCE_APPEND)
    
    claim2 = MonolingualText(text='Flametti ou du dandysme des pauvres', language='fr', prop_nr='P1476')
    claim2.id = 'Q105624761$CDEF-0123-4567'
    claims.add(claim2, action_if_exists=ActionIfExists.FORCE_APPEND)
    
    # Verify we have 2 claims
    assert len(claims.get('P1476')) == 2
    
    # Now user adds new English title (like in the issue)
    claim3 = MonolingualText(text='Flametti, or The Dandyism of the Poor', language='en', prop_nr='P1476')
    claims.add(claim3)  # Using default behavior
    
    # All three claims should exist
    p1476_claims = claims.get('P1476')
    assert len(p1476_claims) == 3, f"Expected 3 claims but got {len(p1476_claims)}"
    
    # None should be marked as removed
    assert all(not c.removed for c in p1476_claims), "No existing claims should be marked as removed"
    
    # Verify JSON output includes all three claims
    json_data = claims.get_json()
    assert 'P1476' in json_data
    assert len(json_data['P1476']) == 3
    
    # Verify no claims marked for removal
    removed_claims = [c for c in json_data['P1476'] if 'remove' in c]
    assert len(removed_claims) == 0, "No claims should be marked for removal"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
