from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item, String
from wikibaseintegrator.models import Aliases, Claims, Descriptions, Form, Forms, Glosses, Labels, Lemmas, Qualifiers, Reference, Representations, Sense, Senses, Sitelinks, Snaks

wbi = WikibaseIntegrator()


# An empty container is falsy (it has a __len__): `container or Container()` replaced the one given by a new one, and the
# changes made afterwards to the given one were lost


def test_entity_keeps_the_empty_containers_given():
    labels, descriptions, aliases, claims, sitelinks = Labels(), Descriptions(), Aliases(), Claims(), Sitelinks()
    item = wbi.item.new(labels=labels, descriptions=descriptions, aliases=aliases, claims=claims, sitelinks=sitelinks)

    assert item.labels is labels and item.descriptions is descriptions and item.aliases is aliases
    assert item.claims is claims and item.sitelinks is sitelinks

    labels.set('en', 'Hello')
    claims.add(String(prop_nr='P1', value='x'))
    json_data = item.get_json()
    assert json_data['labels'] == {'en': {'language': 'en', 'value': 'Hello'}}
    assert list(json_data['claims']) == ['P1']


def test_lexeme_keeps_the_empty_containers_given():
    lemmas, forms, senses = Lemmas(), Forms(), Senses()
    lexeme = wbi.lexeme.new(lemmas=lemmas, forms=forms, senses=senses)

    assert lexeme.lemmas is lemmas and lexeme.forms is forms and lexeme.senses is senses
    lemmas.set('en', 'word')
    assert lexeme.get_json()['lemmas'] == {'en': {'language': 'en', 'value': 'word'}}


def test_claim_keeps_the_empty_qualifiers_given():
    qualifiers = Qualifiers()
    claim = Item(prop_nr='P1', value='Q1', qualifiers=qualifiers)

    assert claim.qualifiers is qualifiers
    qualifiers.add(String(prop_nr='P2', value='y'))
    assert list(claim.get_json()['qualifiers']) == ['P2']


def test_form_sense_and_reference_keep_the_empty_containers_given():
    representations, form_claims = Representations(), Claims()
    form = Form(representations=representations, claims=form_claims)
    assert form.representations is representations and form.claims is form_claims

    glosses, sense_claims = Glosses(), Claims()
    sense = Sense(glosses=glosses, claims=sense_claims)
    assert sense.glosses is glosses and sense.claims is sense_claims

    snaks = Snaks()
    assert Reference(snaks=snaks).snaks is snaks


def test_new_containers_by_default():
    item = wbi.item.new()
    other = wbi.item.new()

    assert isinstance(item.labels, Labels) and item.labels is not other.labels
    assert isinstance(item.claims, Claims) and item.claims is not other.claims
