# Examples

More sample code (adding an entity, a lexeme, etc.) is in the [Jupyter notebooks](https://github.com/LeMyst/WikibaseIntegrator/tree/master/notebooks) of the repository.

In order to create a minimal bot based on WikibaseIntegrator, two things are required:

* A datatype object containing a value.
* An entity object (Item/Property/Lexeme/...) which takes the data, does the checks and performs write.

An optional Login object can be used to be authenticated on the Wikibase instance.

## Create a new Item

```python
from wikibaseintegrator import wbi_login, WikibaseIntegrator
from wikibaseintegrator.datatypes import ExternalID
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login_instance)

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = ExternalID(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to
data = [entrez_gene_id]

# Create a new item
item = wbi.item.new()

# Set an english label
item.labels.set(language='en', value='Newly created item')

# Set a French description
item.descriptions.set(language='fr', value='Une description un peu longue')

item.claims.add(data)
item.write()
```

## Modify an existing item

```python
from wikibaseintegrator import wbi_login, WikibaseIntegrator
from wikibaseintegrator.datatypes import ExternalID
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login_instance)

# data type object, e.g. for a NCBI gene entrez ID
entrez_gene_id = ExternalID(value='<some_entrez_id>', prop_nr='P351')

# data goes into a list, because many data objects can be provided to
data = [entrez_gene_id]

# Search and then edit an Item
item = wbi.item.get(entity_id='Q141806')

# Set an english label but don't modify it if there is already an entry
item.labels.set(language='en', value='An updated item', action_if_exists=ActionIfExists.KEEP)

# Set a French description and replace the existing one
item.descriptions.set(language='fr', value='Une description un peu longue', action_if_exists=ActionIfExists.REPLACE_ALL)

# Add the claims, the existing claims with the same property are kept
item.claims.add(data)

# To replace all the existing claims with the same property instead, use ActionIfExists.REPLACE_ALL
# item.claims.add(data, action_if_exists=ActionIfExists.REPLACE_ALL)

item.write()
```

## A bot for Mass Import

An enhanced example of the previous bot puts the creation of the data and the entity into a 'for loop' and so allows
mass creation or modification of items.

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Item, String, Time
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseTimePrecision

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl Gene IDs
raw_data = {
    '50943': 'ENST00000376197',
    '1029': 'ENST00000498124'
}

wbi = WikibaseIntegrator(login=login_instance)

for entrez_id, ensembl in raw_data.items():
    # add some references
    references = [
        [
            Item(value='Q20641742', prop_nr='P248'),
            Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', precision=WikibaseTimePrecision.DAY),
            ExternalID(value='1017', prop_nr='P351')
        ]
    ]

    # data type object
    entrez_gene_id = String(value=entrez_id, prop_nr='P351', references=references)
    ensembl_transcript_id = String(value=ensembl, prop_nr='P704', references=references)

    # data goes into a list, because many data objects can be provided to
    data = [entrez_gene_id, ensembl_transcript_id]

    # Search for and then edit/create new item
    item = wbi.item.new()
    item.claims.add(data)
    item.write()
```

## Replace a property by another

This bot moves every statement using a property (`OLD_PROPERTY`) to another property with the same datatype
(`NEW_PROPERTY`), on all the entities of a Wikibase instance. Each statement is copied with its value, qualifiers,
references and rank to the new property, then the original statement is removed, in a single edit per entity.

```python
from copy import deepcopy

from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_helpers import execute_sparql_query, generate_entity_instances

wbi_config['USER_AGENT'] = 'MyWikibaseBot/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

OLD_PROPERTY = 'P1234'  # The property to replace
NEW_PROPERTY = 'P5678'  # The property to use instead
DRY_RUN = True  # Set to False to write the changes

# login object
login_instance = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login_instance)

# The values are copied as they are, so both properties must use the same datatype
old_datatype = wbi.property.get(OLD_PROPERTY).datatype
new_datatype = wbi.property.get(NEW_PROPERTY).datatype
if old_datatype != new_datatype:
    raise ValueError(f'{OLD_PROPERTY} ({old_datatype}) and {NEW_PROPERTY} ({new_datatype}) use different datatypes')

# Find the entities holding at least one statement with the old property
query = f'SELECT DISTINCT ?entity WHERE {{ ?entity <{wbi_config["WIKIBASE_URL"]}/prop/{OLD_PROPERTY}> ?statement . }}'
results = execute_sparql_query(query)
entity_ids = [result['entity']['value'].rsplit('/', 1)[-1] for result in results['results']['bindings']]
# The statements of the forms and senses of a lexeme (L1-F1, L1-S1) are not handled by this example
entity_ids = [entity_id for entity_id in entity_ids if '-' not in entity_id]
print(f'{len(entity_ids)} entities use {OLD_PROPERTY}')

# Retrieve the entities 50 by 50, the maximum of the wbgetentities API action
for start in range(0, len(entity_ids), 50):
    for entity_id, entity in generate_entity_instances(entities=entity_ids[start:start + 50], login=login_instance):
        for claim in entity.claims.get(OLD_PROPERTY):
            # Copy the statement to the new property, as a new statement
            new_claim = deepcopy(claim)
            new_claim.reset_id()
            new_claim.mainsnak.property_number = NEW_PROPERTY
            # Not added twice if the entity already holds the same value with the new property
            entity.claims.add(new_claim)

            # Remove the original statement
            claim.remove()

        if DRY_RUN:
            print(f'{entity_id}: {len(entity.claims.get(OLD_PROPERTY))} statement(s) to move')
        else:
            entity.write(summary=f'Replace {OLD_PROPERTY} by {NEW_PROPERTY}', is_bot=True)
```

> [!NOTE]
> The SPARQL endpoint can lag behind the live data: run the bot again until no entity is found. This example only
> moves the main statements: the qualifiers and references using the old property are left untouched.
