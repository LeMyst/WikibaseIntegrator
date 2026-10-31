# Entities

## The Core Parts

WikibaseIntegrator supports two modes in which it can be used, a normal mode, updating each item at a time, and a fast
run mode, which preloads some data locally and then just updates items if the new data provided differs from Wikidata.
The latter mode allows for great speedups when tens of thousands of Wikidata elements need to be checked for updates,
but only a small number will eventually be updated, a situation typically encountered when synchronising Wikidata with
an external resource.

### Entity manipulation

WikibaseIntegrator supports the manipulation of Item, Property, Lexeme and MediaInfo entities through these classes:

* wikibaseintegrator.entities.item.ItemEntity
* wikibaseintegrator.entities.property.PropertyEntity
* wikibaseintegrator.entities.lexeme.LexemeEntity
* wikibaseintegrator.entities.mediainfo.MediaInfoEntity (beta,
  see [Structured Data on Commons](mediainfo.md))

Features:

* Loading a Wikibase entity based on its Wikibase entity ID.
* All Wikibase data types are implemented (and some data types implemented by extensions).
* Full access to the entire Wikibase entity in the form of a JSON dict representation.

## Common use cases

### Read an existing entity

Get the entity with the QID Q582 from the instance.

From [import_entity.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/import_entity.ipynb)

```python
entity = wbi.item.get('Q582')
```

### Start a new entity

Start a new local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
entity = wbi.item.new()
```

### Write an entity to instance

Write a local entity to the instance.

From [import_entity.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/import_entity.ipynb)

```python
entity.write()
```

### Add labels

Add an English and a French label to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
entity.labels.set('en', 'New item')
entity.labels.set('fr', 'Nouvel élément')
```

### Get label value

Get the english label value of the local entity.

From [item_get.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_get.ipynb)

```python
entity.labels.get('en').value
```

### Add aliases

Add an English and a French alias to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
entity.aliases.set('en', 'Item')
entity.aliases.set('fr', 'Élément')
```

`aliases.add()` adds one or more aliases while keeping the existing ones. An alias that is already present is left as it is.

```python
entity.aliases.add('en', ['Item', 'Thing'])
```

### Add descriptions

Add an English and a French description to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
entity.descriptions.set('en', 'A freshly created element')
entity.descriptions.set('fr', 'Un élément fraichement créé')
```

### Add a simple claim

Add a Time claim with the property P74 and the current time to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
claim_time = datatypes.Time(prop_nr='P74', time='now')

entity.claims.add(claim_time)
```

### Get claim value

Get the value of the first claim with the property P2048 of the local entity.

From [item_get.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_get.ipynb)

```python
entity.claims.get('P2048')[0].mainsnak.datavalue['value']['amount']
```

### Manipulate claim, add a qualifier

* Initialize a new Qualifiers object, add a String qualifier with the property P828 and the value 'Item qualifier' to the Qualifiers object.
* Create a String claim with the property P31533 and the value 'A String property' with the previously created Qualifiers object as qualifiers.
* Add the newly created claim to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
qualifiers = Qualifiers()
qualifiers.add(datatypes.String(prop_nr='P828', value='Item qualifier'))

claim_string = datatypes.String(prop_nr='P31533', value='A String property', qualifiers=qualifiers)
entity.claims.add(claim_string)
```

### Manipulate claim, add references

* Initialize a new References object.
* Initialize a new Reference object, add a String reference with the property P828 and the value 'Item string reference' to the Reference object.
* Initialize a new Reference object, add a String reference with the property P828 and the value 'Another item string reference' to the Reference object.
* Add the newly created Reference objects to the References object.
* Create a String claim with the property P31533 and the value 'A String property' with the previously created References object as references.
* Add the newly created claim to the local entity.

From [item_create_new.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/item_create_new.ipynb)

```python
references = References()
reference1 = Reference()
reference1.add(datatypes.String(prop_nr='P828', value='Item string reference'))

reference2 = Reference()
reference2.add(datatypes.String(prop_nr='P828', value='Another item string reference'))

references.add(reference1)
references.add(reference2)

claim_string = datatypes.String(prop_nr='P31533', value='A String property', references=references)
entity.claims.add(claim_string)
```

### Remove a specific claim

Remove all claims with the property P31533 and the value Q123 from the local entity.

```python
claims = entity.claims.get('P31533')
for claim in claims:
    if claim.mainsnak.datavalue['value']['id'] == 'Q123':
        claim.remove()
```

### Get lemma on lexeme

Get all French lemmas of the lexeme.

```python
lexeme.lemmas.get(language='fr')
```

### Set lemma on lexeme

Add a French lemma with the value 'réponse' to the lexeme.

From [lexeme_update.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/lexeme_update.ipynb)

```python
lexeme.lemmas.set(language='fr', value='réponse')
```

### Add gloss to a sense on lexeme

* Create a new Sense object.
* Add an English gloss with the value 'English gloss' to the Sense object.
* Add a French gloss with the value 'French gloss' to the Sense object.
* Create a String claim with the property P828 and the value 'Create a string claim for sense'.
* Add the newly created claim to the Sense object.
* Add the newly created Sense object to the lexeme.

From [lexeme_write.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/lexeme_write.ipynb)

```python
sense = Sense()
sense.glosses.set(language='en', value='English gloss')
sense.glosses.set(language='fr', value='French gloss')
claim = datatypes.String(prop_nr='P828', value="Create a string claim for sense")
sense.claims.add(claim)
lexeme.senses.add(sense)
```

### Add form to a lexeme

* Create a new Form object.
* Add an English form representation with the value 'English form representation' to the Form object.
* Add a French form representation with the value 'French form representation' to the Form object.
* Create a String claim with the property P828 and the value 'Create a string claim for form'.
* Add the newly created claim to the Form object.
* Add the newly created Form object to the lexeme.

From [lexeme_write.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/lexeme_write.ipynb)

```python
form = Form()
form.representations.set(language='en', value='English form representation')
form.representations.set(language='fr', value='French form representation')
claim = datatypes.String(prop_nr='P828', value="Create a string claim for form")
form.claims.add(claim)
lexeme.forms.add(form)
```

### Add a form or a sense to an existing lexeme

Contrary to `write()`, `write_form()` and `write_sense()` only send the new Form or Sense to the Wikibase instance (with
the `wbladdform` and `wbladdsense` actions), the rest of the lexeme is left untouched. They return the id assigned by the
instance, which is also set on the object.

`write_forms()` and `write_senses()` add every Form or Sense of the lexeme without an id, one request per Form or Sense.

From [lexeme_write.ipynb](https://github.com/LeMyst/WikibaseIntegrator/blob/master/notebooks/lexeme_write.ipynb)

```python
lexeme = wbi.lexeme.get('L5')

form = Form()
form.representations.set(language='en', value='English form representation')
form.grammatical_features = ['Q146786']
lexeme.write_form(form)  # 'L5-F3'

sense = Sense()
sense.glosses.set(language='en', value='English gloss')
lexeme.senses.add(sense)
lexeme.write_senses()  # ['L5-S2']
```
