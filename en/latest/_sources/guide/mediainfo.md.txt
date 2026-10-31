# Structured Data on Commons

WikibaseIntegrator supports SDC (Structured Data on Commons) to update a media file hosted on Wikimedia Commons.

> [!WARNING]
> **The MediaInfo support is in beta.** Unlike [MediaWiki](https://www.mediawiki.org/wiki/Stable_interface_policy) and
> [Wikidata](https://www.wikidata.org/wiki/Wikidata:Stable_Interface_Policy), Structured Data on Commons has no stable
> interface policy ([T149410](https://phabricator.wikimedia.org/T149410)) and its API is not versioned, so it can change
> without notice. `MediaInfoEntity` (`wbi.mediainfo`) follows these changes and may change in a minor release, without
> a deprecation period. The Commons-related datatypes used on Wikidata (CommonsMedia, GeoShape, TabularData) are not
> affected.

> [!IMPORTANT]
> To ease the compatibility between Wikidata and Wikimedia Commons, the MediaInfo entity use the "claims" field instead of the "statements" from the API.
> When you read a MediaInfo entity, the "claims" field will be filled with the data from the "statements" field.
> When you write a MediaInfo entity, the "claims" field will be replaced by the "statements" field.

## Retrieve data

```python
from wikibaseintegrator import WikibaseIntegrator

wbi = WikibaseIntegrator()
media = wbi.mediainfo.get('M16431477')

# Retrieve the first "depicts" (P180) claim
print(media.claims.get('P180')[0].mainsnak.datavalue['value']['id'])
```

## Write data

```python
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item

wbi = WikibaseIntegrator()
media = wbi.mediainfo.get('M16431477')

# Add the "depicts" (P180) claim
media.claims.add(Item(prop_nr='P180', value='Q3146211'))

media.write()
```

To query Structured Data on Commons with SPARQL, or to use the fast run mode with MediaInfo entities, see
[Wikimedia Commons Query Service](helpers.md#wikimedia-commons-query-service).
