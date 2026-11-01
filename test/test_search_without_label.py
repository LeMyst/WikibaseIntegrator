from wikibaseintegrator.wbi_helpers import search_entities


def test_result_without_label(wikibase):
    # wbsearchentities only gives a label when the entity has one in the language or its fallbacks (SearchEntities.php),
    # e.g. an entity found by its ID
    wikibase.search_results = [
        {'id': 'Q1', 'title': 'Q1', 'match': {'type': 'entityId', 'text': 'Q1'}, 'display': {}, 'aliases': ['Q1']},
        {'id': 'Q2', 'title': 'Q2', 'label': 'Universe', 'description': 'everything', 'match': {'type': 'label', 'language': 'en', 'text': 'Universe'},
         'display': {'label': {'value': 'Universe', 'language': 'en'}}},
    ]

    results = search_entities('Q1', dict_result=True, allow_anonymous=True)

    assert results[0] == {'id': 'Q1', 'label': None, 'match': {'type': 'entityId', 'text': 'Q1'}, 'description': None, 'aliases': ['Q1']}
    assert results[1]['label'] == 'Universe' and results[1]['description'] == 'everything' and results[1]['aliases'] is None
