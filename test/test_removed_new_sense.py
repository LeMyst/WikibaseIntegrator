from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.models import Sense, Senses

wbi = WikibaseIntegrator()


def new_sense(gloss: str) -> Sense:
    sense = Sense()
    sense.glosses.set('en', gloss)
    return sense


def test_new_sense_removed_before_the_write_is_not_sent():
    lexeme = wbi.lexeme.new()
    sense = new_sense('removed')
    lexeme.senses.add(sense)
    lexeme.senses.add(new_sense('kept'))
    sense.remove()

    # It used to be sent with both 'add' and 'remove'
    assert [json_data['glosses']['en']['value'] for json_data in lexeme.get_json()['senses']] == ['kept']
    assert all('remove' not in json_data for json_data in lexeme.get_json()['senses'])


def test_existing_sense_removed_is_sent_for_removal():
    senses = Senses().from_json([{'id': 'L1-S1', 'glosses': {'en': {'language': 'en', 'value': 'meaning'}}, 'claims': {}}])
    senses.get('L1-S1').remove()

    assert senses.get_json() == [{'id': 'L1-S1', 'glosses': {'en': {'language': 'en', 'value': 'meaning'}}, 'claims': {}, 'remove': ''}]
