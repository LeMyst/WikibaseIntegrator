Data types
==========

One class per Wikibase data type, to create the value of a claim, a qualifier or a reference. Import them from ``wikibaseintegrator.datatypes``. They are claims: see :class:`~wikibaseintegrator.models.claim.Claim` for the members they share.

.. currentmodule:: wikibaseintegrator.datatypes

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~basedatatype.BaseDataType
   ~commonsmedia.CommonsMedia
   ~entityschema.EntitySchema
   ~externalid.ExternalID
   ~form.Form
   ~geoshape.GeoShape
   ~globecoordinate.GlobeCoordinate
   ~item.Item
   ~lexeme.Lexeme
   ~math.Math
   ~monolingualtext.MonolingualText
   ~musicalnotation.MusicalNotation
   ~property.Property
   ~quantity.Quantity
   ~sense.Sense
   ~string.String
   ~tabulardata.TabularData
   ~time.Time
   ~url.URL

Extra data types
----------------

Data types of Wikibase extensions, imported from ``wikibaseintegrator.datatypes.extra``.

.. currentmodule:: wikibaseintegrator.datatypes.extra

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~edtf.EDTF
   ~localmedia.LocalMedia
