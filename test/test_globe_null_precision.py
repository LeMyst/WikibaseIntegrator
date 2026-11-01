from wikibaseintegrator.datatypes import GlobeCoordinate
from wikibaseintegrator.models import Claims

# A coordinate without precision: "precision": null is valid in the Wikibase JSON, and old Wikidata coordinates have it
NULL_PRECISION = {'P625': [{'mainsnak': {'snaktype': 'value', 'property': 'P625', 'datatype': 'globe-coordinate',
                                         'datavalue': {'value': {'latitude': 3.0, 'longitude': 4.0, 'altitude': None, 'precision': None,
                                                                 'globe': 'http://www.wikidata.org/entity/Q2'}, 'type': 'globecoordinate'}},
                            'type': 'statement', 'id': 'Q1$abc', 'rank': 'normal'}]}


def test_compare_with_a_null_precision():
    existing = Claims().from_json(NULL_PRECISION).get('P625')[0]

    # round(None) used to raise TypeError
    assert existing != GlobeCoordinate(latitude=3.0, longitude=4.0, precision=0.1, prop_nr='P625')
    assert existing == Claims().from_json(NULL_PRECISION).get('P625')[0]


def test_add_next_to_a_null_precision():
    claims = Claims().from_json(NULL_PRECISION)
    claims.add(GlobeCoordinate(latitude=5.0, longitude=6.0, precision=0.1, prop_nr='P625'))

    assert len(claims.get_json()['P625']) == 2
