from wikibaseintegrator.datatypes import Item
from wikibaseintegrator.models import Claim, Claims


def test_round_trip_of_a_new_claim():
    claim = Item(value='Q5', prop_nr='P31')
    json_data = claim.get_json()
    # A new claim has no id yet: get_json() leaves it out
    assert 'id' not in json_data

    # Loading it back used to raise KeyError: 'id'
    loaded = Claim().from_json(json_data)
    assert loaded.id is None
    assert loaded.get_json() == json_data


def test_null_id():
    json_data = Item(value='Q5', prop_nr='P31').get_json()
    json_data['id'] = None

    loaded = Claim().from_json(json_data)
    # The id used to become the string 'None', sent as the GUID of the statement
    assert loaded.id is None
    assert 'id' not in loaded.get_json()


def test_claims_of_new_claims():
    claims = Claims().add(Item(value='Q5', prop_nr='P31'))

    assert Claims().from_json(claims.get_json()).get_json() == claims.get_json()


def test_existing_id_is_kept():
    json_data = {**Item(value='Q5', prop_nr='P31').get_json(), 'id': 'Q1$abc'}

    assert Claim().from_json(json_data).id == 'Q1$abc'
