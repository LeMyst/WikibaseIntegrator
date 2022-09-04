from unittest import TestCase

from wikibaseintegrator.wbi_exceptions import ModificationFailed, SaveFailed, SearchError


class TestWbiExceptions(TestCase):
    @staticmethod
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
        assert 'Q582' in modification_failed.get_conflicting_entity_ids
        assert 'en' in modification_failed.get_languages

    def test_invalid_claim(self):
        error_dict = {
            'error': {
                '*': 'See https://test.wikidata.org/w/api.php for API usage. Subscribe to the mediawiki-api-announce mailing list at &lt;https://lists.wikimedia.org/mailman/listinfo/mediawiki-api-announce&gt; for notice of API deprecations and breaking changes.',
                'code': 'invalid-claim',
                'info': "'' is not a valid property ID",
                'messages': [{
                    'name': 'wikibase-api-invalid-claim',
                    'parameters': ["'' is not a valid property ID"],
                    'html': {'*': '<i> is not a valid property ID</i>'}
                }],
            }}

        invalid_claim = ModificationFailed(error_dict['error'])

        assert str(invalid_claim) == '"\'\' is not a valid property ID"'
        assert invalid_claim.code == 'invalid-claim'
        assert invalid_claim.info == "'' is not a valid property ID"
        assert 'wikibase-api-invalid-claim' in invalid_claim.messages_names

    def test_modification_failed_no_dict(self):
        error_dict = {}
        with self.assertRaises(KeyError):
            ModificationFailed(error_dict['error'])

    def test_modification_failed_no_message(self):
        error_dict = {'error': {'*': 'See https://test.wikidata.org/w/api.php for API usage. '
                                     'Subscribe to the mediawiki-api-announce mailing list at '
                                     '&lt;https://lists.wikimedia.org/postorius/lists/mediawiki-api-announce.lists.wikimedia.org/&gt; '
                                     'for notice of API deprecations and breaking changes.',
                                'code': 'modification-failed',
                                'info': 'Item [[Q582|Q582]] already has label "MODIFIED LABEL" '
                                        'associated with language code en, using the same '
                                        'description text.'
                                },
                      'servedby': 'mw1375'}

        exception = ModificationFailed(error_dict['error'])
        assert 'wikibaseintegrator-missing-messages' in exception.messages_names

    def test_failed_save_no_conflict(self):
        error_dict = {'error': {'*': 'See https://test.wikidata.org/w/api.php for API usage. '
                                     'Subscribe to the mediawiki-api-announce mailing list at '
                                     '&lt;https://lists.wikimedia.org/postorius/lists/mediawiki-api-announce.lists.wikimedia.org/&gt; '
                                     'for notice of API deprecations and breaking changes.',
                                'code': 'failed-save',
                                'info': 'The save has failed.',
                                'messages': [{'html': {'*': 'The save has failed.'},
                                              'name': 'wikibase-api-failed-save',
                                              'parameters': []}]},
                      'servedby': 'mw1425'}

        failed_save = SaveFailed(error_dict['error'])

        assert failed_save.get_conflicting_entity_ids == []

    def test_modification_failed_no_parameters(self):
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
                                              }]},
                      'servedby': 'mw1375'}

        modification_failed = ModificationFailed(error_dict['error'])
        with self.assertRaises(KeyError):
            _ = modification_failed.get_languages

    @staticmethod
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
        assert 'P50' in failed_save.get_conflicting_entity_ids
        assert len(failed_save.get_conflicting_entity_ids) == 1
        assert 'en' in failed_save.get_languages

    @staticmethod
    def test_searcherror():
        assert str(SearchError('SearchError')) == 'SearchError'

    def test_modification_failed_error_dict(self):
        error_dict = {'error': {}}

        exception = ModificationFailed(error_dict['error'])
        assert 'wikibaseintegrator-missing-messages' in exception.messages_names
        assert exception.info == 'MWApiError'
        assert exception.code == 'wikibaseintegrator-missing-error-code'
