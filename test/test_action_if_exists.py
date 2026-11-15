"""
action_if_exists of the add() methods of the models other than Claims (#1191): the same semantics as Claims.add().
"""
import pytest

from wikibaseintegrator import datatypes
from wikibaseintegrator.models import Form, Forms, Qualifiers, Reference, References, Sense, Senses, Snak
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.wbi_enums import ActionIfExists


def snak(prop_nr='P1', value='a'):
    return Snak().from_json(datatypes.String(prop_nr=prop_nr, value=value).get_json()['mainsnak'])


def values(snaks):
    return [(s.property_number, s.datavalue['value']) for s in snaks]


class TestSnaks:
    """The qualifiers of a claim and the snaks of a reference: per property, like the claims of an entity."""

    @staticmethod
    def build(kind):
        container = Qualifiers() if kind == 'qualifiers' else Reference()
        for prop_nr, value in (('P1', 'a'), ('P1', 'b'), ('P2', 'c')):
            container.add(snak(prop_nr, value))
        return container

    @pytest.mark.parametrize('kind', ['qualifiers', 'reference'])
    @pytest.mark.parametrize('action, new, expected', [
        (ActionIfExists.APPEND_OR_REPLACE, ('P1', 'a'), [('P1', 'a'), ('P1', 'b'), ('P2', 'c')]),
        (ActionIfExists.APPEND_OR_REPLACE, ('P1', 'd'), [('P1', 'a'), ('P1', 'b'), ('P1', 'd'), ('P2', 'c')]),
        (ActionIfExists.MERGE_REFS_OR_APPEND, ('P1', 'a'), [('P1', 'a'), ('P1', 'b'), ('P2', 'c')]),
        (ActionIfExists.MERGE_REFS_OR_APPEND, ('P1', 'd'), [('P1', 'a'), ('P1', 'b'), ('P1', 'd'), ('P2', 'c')]),
        (ActionIfExists.FORCE_APPEND, ('P1', 'a'), [('P1', 'a'), ('P1', 'b'), ('P1', 'a'), ('P2', 'c')]),
        (ActionIfExists.KEEP, ('P1', 'd'), [('P1', 'a'), ('P1', 'b'), ('P2', 'c')]),
        (ActionIfExists.KEEP, ('P3', 'd'), [('P1', 'a'), ('P1', 'b'), ('P2', 'c'), ('P3', 'd')]),
        (ActionIfExists.REPLACE_ALL, ('P1', 'a'), [('P1', 'a'), ('P2', 'c')]),
        (ActionIfExists.REPLACE_ALL, ('P1', 'd'), [('P1', 'd'), ('P2', 'c')]),
    ])
    def test_add(self, kind, action, new, expected):
        container = self.build(kind)
        container.add(snak(*new), action_if_exists=action)
        assert values(container) == expected

    @pytest.mark.parametrize('kind', ['qualifiers', 'reference'])
    def test_default_is_append_or_replace(self, kind):
        container = self.build(kind)
        container.add(snak('P1', 'a'))
        assert values(container) == [('P1', 'a'), ('P1', 'b'), ('P2', 'c')]

    def test_replace_all_keeps_the_equal_snak(self):
        qualifiers = self.build('qualifiers')
        existing = qualifiers.get('P1')[0]
        qualifiers.add(snak('P1', 'a'), action_if_exists=ActionIfExists.REPLACE_ALL)
        assert qualifiers.get('P1') == [existing]
        assert qualifiers.get('P1')[0] is existing

    def test_a_claim_is_compared_by_its_main_snak(self):
        qualifiers = self.build('qualifiers')
        qualifiers.add(datatypes.String(prop_nr='P1', value='a'))
        assert values(qualifiers) == [('P1', 'a'), ('P1', 'b'), ('P2', 'c')]

    @pytest.mark.parametrize('kind', ['qualifiers', 'reference'])
    def test_invalid_action(self, kind):
        with pytest.raises(ValueError, match='not a valid action_if_exists'):
            self.build(kind).add(snak('P1', 'd'), action_if_exists='KEEP')

    def test_set_and_from_json_keep_every_qualifier(self):
        # set() replaces the qualifiers with the given ones, and from_json() reads them as they are on the instance
        assert values(Qualifiers().set([snak(), snak()])) == [('P1', 'a'), ('P1', 'a')]
        json_data = {'P1': [snak().get_json(), snak().get_json()]}
        assert values(Qualifiers().from_json(json_data)) == [('P1', 'a'), ('P1', 'a')]


def reference(*snak_values):
    built = Reference()
    for value in snak_values:
        built.add(snak('P1', value))
    return built


class TestReferences:
    """The references of a claim: the whole list, as references have no property."""

    @staticmethod
    def build():
        references = References()
        first = reference('a')
        first.hash = 'hash-a'
        return references.add(first).add(reference('b'))

    @staticmethod
    def contents(references):
        return [[s.datavalue['value'] for s in r] for r in references]

    @pytest.mark.parametrize('action, new, expected', [
        (ActionIfExists.APPEND_OR_REPLACE, ('a',), [['a'], ['b']]),
        (ActionIfExists.APPEND_OR_REPLACE, ('c',), [['a'], ['b'], ['c']]),
        (ActionIfExists.MERGE_REFS_OR_APPEND, ('a',), [['a'], ['b']]),
        (ActionIfExists.FORCE_APPEND, ('a',), [['a'], ['b'], ['a']]),
        (ActionIfExists.KEEP, ('c',), [['a'], ['b']]),
        (ActionIfExists.REPLACE_ALL, ('a',), [['a']]),
        (ActionIfExists.REPLACE_ALL, ('c', 'd'), [['c', 'd']]),
    ])
    def test_add(self, action, new, expected):
        references = self.build()
        references.add(reference(*new), action_if_exists=action)
        assert self.contents(references) == expected

    def test_keep_adds_the_first_reference(self):
        references = References().add(reference('a'), action_if_exists=ActionIfExists.KEEP)
        assert self.contents(references) == [['a']]

    def test_replace_all_keeps_the_equal_reference(self):
        references = self.build()
        references.add(reference('a'), action_if_exists=ActionIfExists.REPLACE_ALL)
        # The reference of the instance, with its hash
        assert [r.hash for r in references] == ['hash-a']

    def test_from_json_keeps_every_reference(self):
        json_data = [{'hash': 'h1', 'snaks': {'P1': [snak().get_json()]}, 'snaks-order': ['P1']},
                     {'hash': 'h2', 'snaks': {'P1': [snak().get_json()]}, 'snaks-order': ['P1']}]
        assert [r.hash for r in References().from_json(json_data)] == ['h1', 'h2']


def form(form_id=None, value='a'):
    built = Form(form_id=form_id)
    built.representations.set(language='en', value=value)
    return built


def sense(sense_id=None, value='a'):
    built = Sense(sense_id=sense_id)
    built.glosses.set(language='en', value=value)
    return built


def text(sub_entity):
    return (sub_entity.representations if isinstance(sub_entity, Form) else sub_entity.glosses).get('en').value


@pytest.fixture(params=['forms', 'senses'])
def kind(request):
    return request.param


class TestFormsAndSenses:
    """The forms and the senses of a lexeme: they have an id and can be marked for removal, like the claims."""

    @staticmethod
    def new(kind, sub_entity_id=None, value='a'):
        if kind == 'forms':
            return form(f'L1-F{sub_entity_id}' if sub_entity_id else None, value)
        return sense(f'L1-S{sub_entity_id}' if sub_entity_id else None, value)

    def build(self, kind):
        collection = Forms() if kind == 'forms' else Senses()
        collection.add(self.new(kind, 1, 'a')).add(self.new(kind, 2, 'b'))
        return collection

    @staticmethod
    def state(collection):
        return [(sub_entity.id[-1] if sub_entity.id else None, text(sub_entity), sub_entity.removed) for sub_entity in collection]

    @pytest.mark.parametrize('action', [ActionIfExists.APPEND_OR_REPLACE, ActionIfExists.MERGE_REFS_OR_APPEND])
    @pytest.mark.parametrize('new, expected', [
        # The same content without an id: already there
        ((None, 'a'), [('1', 'a', False), ('2', 'b', False)]),
        # The same id: replaced in place
        ((1, 'c'), [('1', 'c', False), ('2', 'b', False)]),
        # Another id, even with the same content: another one
        ((3, 'a'), [('1', 'a', False), ('2', 'b', False), ('3', 'a', False)]),
        ((None, 'c'), [('1', 'a', False), ('2', 'b', False), (None, 'c', False)]),
    ], ids=['same-content', 'same-id', 'other-id', 'new'])
    def test_append_or_replace(self, kind, action, new, expected):
        collection = self.build(kind)
        collection.add(self.new(kind, *new), action_if_exists=action)
        assert self.state(collection) == expected

    def test_default_is_append_or_replace(self, kind):
        collection = self.build(kind)
        collection.add(self.new(kind, None, 'a'))
        assert len(collection) == 2

    def test_adding_cancels_the_removal(self, kind):
        collection = self.build(kind)
        next(iter(collection)).remove()
        collection.add(self.new(kind, None, 'a'))
        assert self.state(collection) == [('1', 'a', False), ('2', 'b', False)]

    def test_force_append(self, kind):
        collection = self.build(kind)
        collection.add(self.new(kind, None, 'a'), action_if_exists=ActionIfExists.FORCE_APPEND)
        assert self.state(collection) == [('1', 'a', False), ('2', 'b', False), (None, 'a', False)]

    def test_keep(self, kind):
        collection = self.build(kind)
        collection.add(self.new(kind, None, 'c'), action_if_exists=ActionIfExists.KEEP)
        assert len(collection) == 2

        # The ones marked for removal don't count
        for sub_entity in collection:
            sub_entity.remove()
        collection.add(self.new(kind, None, 'c'), action_if_exists=ActionIfExists.KEEP)
        assert self.state(collection) == [('1', 'a', True), ('2', 'b', True), (None, 'c', False)]

    def test_replace_all(self, kind):
        collection = self.build(kind)
        collection.add(self.new(kind, None, 'c'), action_if_exists=ActionIfExists.REPLACE_ALL)
        assert self.state(collection) == [('1', 'a', True), ('2', 'b', True), (None, 'c', False)]
        # The write removes the others and adds the new one, a new one marked for removal is left out
        json_data = collection.get_json()
        assert ['remove' in sub_entity for sub_entity in json_data] == [True, True, False]

    def test_replace_all_keeps_the_same_one(self, kind):
        collection = self.build(kind)
        collection.add(self.new(kind, None, 'a'), action_if_exists=ActionIfExists.REPLACE_ALL)
        assert self.state(collection) == [('1', 'a', False), ('2', 'b', True)]

    def test_invalid_action(self, kind):
        with pytest.raises(ValueError, match='not a valid action_if_exists'):
            self.build(kind).add(self.new(kind), action_if_exists=None)

    def test_from_json_keeps_every_one(self, kind):
        collection = self.build(kind)
        json_data = [sub_entity.get_json() for sub_entity in collection] * 2
        assert len((Forms() if kind == 'forms' else Senses()).from_json(json_data)) == 4


class TestAliases:
    @pytest.mark.parametrize('action', [ActionIfExists.FORCE_APPEND, ActionIfExists.MERGE_REFS_OR_APPEND])
    def test_actions_without_meaning_are_refused(self, action):
        with pytest.raises(ValueError, match='has no meaning for aliases'):
            Aliases().set('en', 'an alias', action_if_exists=action)
