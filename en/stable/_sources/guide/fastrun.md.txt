# Fast run

The fast run mode is designed for bots synchronising an external resource with a Wikibase instance, where most of the
entities are usually already up to date. Instead of loading every entity through the MediaWiki API to compare it with
the local data, the fast run mode loads the current state of the entities of the data corpus with paginated SPARQL
queries, then decides locally, entity per entity, if a write is required. When nothing changed (the most common case),
no MediaWiki API call is made at all for that entity.

In order to use the fast run mode, you need to know the property/value combination which determines the data corpus you
would like to operate on. E.g. for operating on human genes, you need to know
that [P351](https://www.wikidata.org/entity/P351) is the NCBI Entrez Gene ID and you also need to know that you are
dealing with humans, best represented by the [found in taxon property (P703)](https://www.wikidata.org/entity/P703) with
the value [Q15978631](https://www.wikidata.org/entity/Q15978631) for Homo sapiens.

IMPORTANT: In order for the fast run mode to work on entities without a known entity ID, the data you provide must
contain at least one unique value/id only present on one Wikibase entity, e.g. an NCBI entrez gene ID, Uniprot ID, etc.
This unique value is used to identify the target entity. If the entity ID is already known (e.g. the entity was loaded
with `wbi.item.get()`), the comparison is automatically restricted to that entity and this requirement does not apply.

## The base filter

The base filter defines the data corpus and is a list of datatype instances (the same classes used to create claims).
Three forms are supported:

* A property with a value: the entities must have this exact statement, e.g. `Item(prop_nr='P703', value='Q15978631')`
  (found in taxon Homo sapiens).
* A property without a value: the entities must have a statement with this property, whatever the value, e.g.
  `ExternalID(prop_nr='P351')` (any NCBI Entrez Gene ID).
* A property path, given as a list of two datatype instances: the value is reached through the first property followed
  by any number of hops with the second one, e.g. `[Item(prop_nr='P31', value='Q11173'), Item(prop_nr='P279')]`
  (instance of (P31) chemical compound (Q11173), directly or through a chain of subclass of (P279)).

```python
from wikibaseintegrator.datatypes import ExternalID, Item

fast_run_base_filter = [ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')]
```

## Checking if a write is required

The entry point is `entity.write_required()`. It returns `True` if the local entity differs from the live data and an
actual write is needed, `False` if the entity is already up to date and the write can be skipped. The full example, a
modified version of the mass import bot from the normal mode example:

```python
from wikibaseintegrator import WikibaseIntegrator, wbi_login
from wikibaseintegrator.datatypes import ExternalID, Item, Time
from wikibaseintegrator.wbi_enums import WikibaseTimePrecision

# login object
login = wbi_login.OAuth2(consumer_token='<consumer_token>', consumer_secret='<consumer_secret>')

wbi = WikibaseIntegrator(login=login)

fast_run_base_filter = [ExternalID(prop_nr='P351'), ExternalID(prop_nr='P704'), Item(prop_nr='P703', value='Q15978631')]

# We have raw data, which should be written to Wikidata, namely two human NCBI entrez gene IDs mapped to two Ensembl transcript IDs
# You can iterate over any data source as long as you can map the values to Wikidata properties.
raw_data = {
    '50943': 'ENST00000376197',
    '1029': 'ENST00000498124'
}

for entrez_id, ensembl in raw_data.items():
    # add some references
    references = [
        [
            Item(value='Q20641742', prop_nr='P248'),
            Time(time='+2020-02-08T00:00:00Z', prop_nr='P813', precision=WikibaseTimePrecision.DAY)
        ]
    ]

    # data type objects
    entrez_gene_id = ExternalID(value=entrez_id, prop_nr='P351', references=references)
    ensembl_transcript_id = ExternalID(value=ensembl, prop_nr='P704', references=references)

    # data goes into a list, because many data objects can be provided to
    data = [entrez_gene_id, ensembl_transcript_id]

    item = wbi.item.new()
    item.claims.add(data)

    # Compare the local data with the live data and only write when something differs
    if item.write_required(base_filter=fast_run_base_filter):
        item.write()
```

Note: only the claims whose property appears in the base filter are compared. In the example above, the P351 and P704
claims are checked because both properties are part of the base filter; a claim on any other property would be ignored
by the comparison. A write is reported as not required only when one entity (the entity being edited, when its ID is
known) holds all the compared claims.

## Options

`write_required()` accepts optional parameters, forwarded to the fastrun container:

* `use_qualifiers` (default `True`): also compare the qualifiers of the statements.
* `use_references` (default `False`): also compare the references of the statements. By default, references are
  ignored.
* `use_rank` (default `False`): also compare the rank of the statements.
* `case_insensitive` (default `False`): compare string values case-insensitively. The comparison of qualifiers,
  references and ranks stays case sensitive.
* `cache` (default `True`): keep the data returned by the SPARQL endpoint in memory and reuse it for the next
  checks. When disabled, the queries are restricted to the exact values of the claims instead of preloading every
  statement of the property.
* `action_if_exists` (default `ActionIfExists.REPLACE_ALL`): the action that will be used for the write. With
  `FORCE_APPEND`, the statements are always appended and a write is always reported as required. With the other
  actions, the claims must already exist on the entity for the write to be skipped.

The preloaded data is shared: containers are cached at the module level and reused by every `write_required()` call
using the same base filter and options, so the SPARQL queries are only executed once per property.

## Checking labels, descriptions and aliases

`write_required()` only compares claims. To check language data (labels, descriptions or aliases), use the fastrun
container directly:

```python
from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import ExternalID, Item

frc = wbi_fastrun.get_fastrun_container(base_filter=[ExternalID(prop_nr='P351'), Item(prop_nr='P703', value='Q15978631')])

# Resolve the entity ID from a unique value, without any MediaWiki API call
qids = frc.get_entities(claims=[ExternalID(value='50943', prop_nr='P351')])

# Returns True if the English label differs from 'CDK7' and a write is required
frc.check_language_data(qid=qids[0], lang_data=['CDK7'], lang='en', lang_data_type='label')
```

## Limitations

* The SPARQL endpoint can lag behind the live data (typically a few seconds to a few minutes on Wikidata). A write
  that just happened may not be visible yet, and the same write could be reported as required again.
* The attributes missing from the SPARQL simple values are rebuilt with their default value: the bounds of a quantity,
  the precision of a globe coordinate, the timezone and calendar model of a time, etc. Statements using non-default
  attributes are always reported as requiring a write. The precision of a time and the unit of a quantity are loaded
  from the value nodes, so they are compared.
* Math statements are always reported as requiring a write: the RDF export holds the formula rendered as MathML, not
  its TeX source, so the values can't be compared.
* The qualifiers, references and ranks are loaded lazily with one SPARQL query per statement to check, and the units
  and precisions with one query per 100 statements to check. This is fast when most entities are up to date, but can
  slow down the run when many entities hold the same values.

## Performance statistics

Measured on a synchronisation bot of French administrative entities with Wikidata. The "partial fastrun" column is the
mode without cache, where the queries are restricted to the exact values of the claims:

| Dataset                     | partial fastrun | fastrun without qualifiers/references | fastrun with qualifiers | fastrun with qualifiers/references |
|:----------------------------|----------------:|--------------------------------------:|------------------------:|-----------------------------------:|
| Communes (34990 elements)   |               ? |                                  7min |                     30s |                                60s |
| Départements (100 elements) |           70min |                                    1s |                     30s |                                60s |
