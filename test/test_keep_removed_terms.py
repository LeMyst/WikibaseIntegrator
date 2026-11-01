from wikibaseintegrator.datatypes import String
from wikibaseintegrator.models import Aliases, Claims, Labels
from wikibaseintegrator.wbi_enums import ActionIfExists


class TestKeepAfterRemoval:
    """A removed label or alias doesn't count as present for KEEP, like a removed claim for Claims.add()."""

    def test_label(self):
        labels = Labels().from_json({'en': {'language': 'en', 'value': 'old'}})
        labels.set('en', None)

        labels.set('en', 'new', action_if_exists=ActionIfExists.KEEP)

        # The label used to stay removed
        assert labels.get_json() == {'en': {'language': 'en', 'value': 'new'}}

    def test_label_kept(self):
        labels = Labels().from_json({'en': {'language': 'en', 'value': 'old'}})

        labels.set('en', 'new', action_if_exists=ActionIfExists.KEEP)

        assert labels.get_json() == {'en': {'language': 'en', 'value': 'old'}}

    def test_aliases(self):
        aliases = Aliases().from_json({'en': [{'language': 'en', 'value': 'a'}, {'language': 'en', 'value': 'b'}]})
        aliases.set('en', None)

        aliases.set('en', ['c'], action_if_exists=ActionIfExists.KEEP)

        # The aliases used to stay removed: the language has no alias left, the new ones are set
        assert aliases.get_json() == {'en': [{'language': 'en', 'value': 'c'}]}

    def test_aliases_kept(self):
        aliases = Aliases().from_json({'en': [{'language': 'en', 'value': 'a'}]})

        aliases.set('en', ['c'], action_if_exists=ActionIfExists.KEEP)

        assert aliases.get_json() == {'en': [{'language': 'en', 'value': 'a'}]}

    def test_aliases_of_a_new_language(self):
        aliases = Aliases()

        aliases.set('fr', ['c'], action_if_exists=ActionIfExists.KEEP)

        assert aliases.get_json() == {'fr': [{'language': 'fr', 'value': 'c'}]}


class TestClaimsRemoveByNumber:
    def test_remove_with_an_int(self):
        claims = Claims().add(String(prop_nr='P31', value='x'))

        # get() accepted an int, remove() silently did nothing
        claims.remove(31)

        assert claims.get(31) == []
        assert claims.get_json() == {}

    def test_remove_an_existing_claim_with_an_int(self):
        claims = Claims().from_json({'P31': [{'mainsnak': {'snaktype': 'value', 'property': 'P31', 'datatype': 'string', 'datavalue': {'value': 'x', 'type': 'string'}},
                                              'type': 'statement', 'id': 'Q1$abc', 'rank': 'normal'}]})

        claims.remove(31)

        assert claims.get_json()['P31'][0]['remove'] == ''
