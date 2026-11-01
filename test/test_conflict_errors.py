import pytest

from wikibaseintegrator.wbi_exceptions import ModificationFailed, MWApiError, SaveFailed
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

# The parameters of the sitelink conflicts of Wikibase (SiteLinkUniquenessValidator): [sitelink, item], or [sitelink] for an unknown item
SITELINK_CONFLICT = {'name': 'wikibase-validator-sitelink-conflict', 'parameters': ['[https://en.wikipedia.org/wiki/Foo enwiki:Foo]', '[[Q42|Q42]]']}
SITELINK_CONFLICT_REDIRECTS = {'name': 'wikibase-validator-sitelink-conflict-redirects-supported', 'parameters': ['[https://fr.wikipedia.org/wiki/Foo frwiki:Foo]', '[[Q43|Q43]]']}
SITELINK_CONFLICT_UNKNOWN = {'name': 'wikibase-validator-sitelink-conflict-unknown', 'parameters': ['[https://de.wikipedia.org/wiki/Foo dewiki:Foo]']}
LABEL_CONFLICT = {'name': 'wikibase-validator-label-conflict', 'parameters': ['Depiction', 'en', '[[Property:P50|P50]]']}
LABEL_DESCRIPTION_CONFLICT = {'name': 'wikibase-validator-label-with-description-conflict', 'parameters': ['Foo', 'fr', '[[Lexeme:L5|L5]]']}


def failed_save(*messages):
    return SaveFailed({'code': 'failed-save', 'info': 'The save has failed.', 'messages': [{'name': 'wikibase-api-failed-save', 'parameters': []}, *messages]})


class TestConflictingEntities:
    def test_sitelink_conflict(self):
        error = failed_save(SITELINK_CONFLICT)

        assert error.get_conflicting_entity_ids == ['Q42']
        # A sitelink conflict has no language
        assert error.get_languages == []

    def test_sitelink_conflict_variants(self):
        error = failed_save(SITELINK_CONFLICT_REDIRECTS, SITELINK_CONFLICT_UNKNOWN)

        # The conflict with an unknown item names no entity
        assert error.get_conflicting_entity_ids == ['Q43']
        assert error.get_languages == []

    def test_label_conflicts(self):
        error = ModificationFailed({'code': 'modification-failed', 'info': 'Conflict.', 'messages': [LABEL_CONFLICT, LABEL_DESCRIPTION_CONFLICT]})

        # Without the namespace of the entity page
        assert sorted(error.get_conflicting_entity_ids) == ['L5', 'P50']
        assert sorted(error.get_languages) == ['en', 'fr']

    def test_mixed_conflicts(self):
        error = failed_save(LABEL_CONFLICT, SITELINK_CONFLICT)

        assert sorted(error.get_conflicting_entity_ids) == ['P50', 'Q42']
        assert error.get_languages == ['en']

    def test_messages_without_parameters(self):
        error = failed_save({'name': 'wikibase-validator-sitelink-conflict'}, {'name': 'wikibase-validator-label-conflict', 'parameters': []})

        assert error.get_conflicting_entity_ids == []
        assert error.get_languages == []


class TestSitelinkConflictIsSaveFailed:
    @pytest.mark.parametrize('message', [SITELINK_CONFLICT, SITELINK_CONFLICT_REDIRECTS, SITELINK_CONFLICT_UNKNOWN], ids=lambda message: message['name'])
    def test_every_sitelink_conflict_raises_save_failed(self, wikibase, message):
        wikibase.fail_next(code='failed-save', info='The save has failed.', messages=[message])

        with pytest.raises(SaveFailed) as error:
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, allow_anonymous=True)

        assert error.value.messages_names == [message['name']]

    def test_another_failed_save_is_an_mwapierror(self, wikibase):
        wikibase.fail_next(code='failed-save', info='The save has failed.', messages=[{'name': 'wikibase-validator-other'}])

        with pytest.raises(MWApiError) as error:
            mediawiki_api_call_helper(data={'action': 'wbeditentity', 'id': 'Q1', 'format': 'json'}, allow_anonymous=True)

        assert not isinstance(error.value, SaveFailed)
