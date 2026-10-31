# Data types

Currently, Wikibase supports 18 different data types. The data types are represented as their own classes in
wikibaseintegrator.datatypes. Each datatype has its own peculiarities, which means that some of them require special
parameters (e.g. Globe Coordinates). They are available under the namespace `wikibaseintegrator.datatypes`.

The data types currently implemented:

* CommonsMedia
* EntitySchema
* ExternalID
* Form
* GeoShape
* GlobeCoordinate
* Item
* Lexeme
* Math
* MonolingualText
* MusicalNotation
* Property
* Quantity
* Sense
* String
* TabularData
* Time
* URL

Two additional data types are also implemented but require the installation of the MediaWiki extension to work properly:

* extra.EDTF ([Wikibase EDTF](https://www.mediawiki.org/wiki/Extension:Wikibase_EDTF))
* extra.LocalMedia ([Wikibase Local Media](https://www.mediawiki.org/wiki/Extension:Wikibase_Local_Media))

For details of how to create values (=instances) with these data types, please (for now) consult the docstrings in the
source code or the documentation website. Of note, these data type instances hold the values and, if specified, data
type instances for references and qualifiers.

The datatype names used by the Wikibase API are listed in the `wikibaseintegrator.wbi_enums.WikibaseDatatype` enum,
e.g. for a new property: `wbi.property.new(datatype=WikibaseDatatype.ITEM)`. Its members are also strings equal to the
API names (`WikibaseDatatype.ITEM == 'wikibase-item'`), so a plain string works too. Each data type class gives its own
name in `DTYPE` (`Item.DTYPE is WikibaseDatatype.ITEM`). A datatype unknown to WikibaseIntegrator, provided by a
Wikibase extension, is kept as a string.
