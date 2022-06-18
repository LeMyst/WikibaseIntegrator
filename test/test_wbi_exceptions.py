from wikibaseintegrator.wbi_exceptions import ModificationFailed, SaveFailed, SearchError


def test_modification_failed():
    error_dict = {'error': {'*': 'See https://test.wikidata.org/w/api.php for API usage. '
                                 'Subscribe to the mediawiki-api-announce mailing list at '
                                 '&lt;https://lists.wikimedia.org/postorius/lists/mediawiki-api-announce.lists.wikimedia.org/&gt; '
                                 'for notice of API deprecations and breaking changes.',
                            'code': 'modification-failed',
                            'info': 'Item [[Q582|Q582]] already has label "MODIFIED LABEL" '
                                    'associated with language code en, using the same '
                                    'description text.',
                            'messages': [{'html': {'*': 'Item <a href="/wiki/Q582" '
                                                        'title="Q582">Q582</a> already has '
                                                        'label "MODIFIED LABEL" associated with '
                                                        'language code en, using the same '
                                                        'description text.'},
                                          'name': 'wikibase-validator-label-with-description-conflict',
                                          'parameters': ['MODIFIED LABEL',
                                                         'en',
                                                         '[[Q582|Q582]]']}]},
                  'servedby': 'mw1375'}

    modification_failed = ModificationFailed(error_dict['error'])

    assert str(modification_failed) == "'Item [[Q582|Q582]] already has label \"MODIFIED LABEL\" associated with language code en, using the same description text.'"
    assert modification_failed.code == 'modification-failed'
    assert modification_failed.info == 'Item [[Q582|Q582]] already has label "MODIFIED LABEL" associated with language code en, using the same description text.'
    assert 'wikibase-validator-label-with-description-conflict' in modification_failed.messages_names


def test_failed_save():
    error_dict = {'error': {'*': 'See https://test.wikidata.org/w/api.php for API usage. '
                                 'Subscribe to the mediawiki-api-announce mailing list at '
                                 '&lt;https://lists.wikimedia.org/postorius/lists/mediawiki-api-announce.lists.wikimedia.org/&gt; '
                                 'for notice of API deprecations and breaking changes.',
                            'code': 'failed-save',
                            'info': 'The save has failed.',
                            'messages': [{'html': {'*': 'The save has failed.'},
                                          'name': 'wikibase-api-failed-save',
                                          'parameters': []},
                                         {'html': {'*': 'Property <a href="/wiki/Property:P50" '
                                                        'title="Property:P50">P50</a> already '
                                                        'has label "Depiction" associated with '
                                                        'language code en.'},
                                          'name': 'wikibase-validator-label-conflict',
                                          'parameters': ['Depiction',
                                                         'en',
                                                         '[[Property:P50|P50]]']},
                                         {'html': {'*': 'Property <a href="/wiki/Property:P50" '
                                                        'title="Property:P50">P50</a> already '
                                                        'has label "representación" associated '
                                                        'with language code es.'},
                                          'name': 'wikibase-validator-label-conflict',
                                          'parameters': ['representación',
                                                         'es',
                                                         '[[Property:P50|P50]]']}]},
                  'servedby': 'mw1425'}

    failed_save = SaveFailed(error_dict['error'])

    assert str(failed_save) == "'The save has failed.'"
    assert failed_save.code == 'failed-save'
    assert failed_save.info == 'The save has failed.'
    assert 'wikibase-api-failed-save' in failed_save.messages_names


def test_searcherror():
    assert str(SearchError('SearchError')) == 'SearchError'
