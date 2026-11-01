Configuration, enums and exceptions
===================================

The global options, the enumerations of the API values, the exceptions, the retries, the WikibaseManifest of an instance and the EditGroups.

Configuration
-------------

.. automodule:: wikibaseintegrator.wbi_config
   :no-members:

Enums
-----

.. currentmodule:: wikibaseintegrator.wbi_enums

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~ActionIfExists
   ~EntityField
   ~WikibaseDatatype
   ~WikibaseRank
   ~WikibaseSnakType
   ~WikibaseTimePrecision

Exceptions
----------

.. currentmodule:: wikibaseintegrator.wbi_exceptions

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~WikibaseIntegratorError
   ~MWApiError
   ~ModificationFailed
   ~SaveFailed
   ~NonExistentEntityError
   ~MissingExtensionError
   ~MissingEntityException
   ~EmptyValueError
   ~UnknownDatatypeError
   ~AnonymousEditNotAllowedError
   ~LoginError
   ~SearchError
   ~MaxRetriesReachedException
   ~WCQSAuthenticationError
   ~MaxRetriesReachedException
   ~SearchError
   ~WCQSAuthenticationError

Retries
-------

.. currentmodule:: wikibaseintegrator.wbi_backoff

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~wbi_backoff
   ~RetryAfterError
   ~wbi_backoff_wait
   ~wbi_backoff_giveup

WikibaseManifest
----------------

.. automodule:: wikibaseintegrator.wbi_manifest
   :no-members:

.. currentmodule:: wikibaseintegrator.wbi_manifest

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~get_manifest
   ~WikibaseManifest
   ~manifest_url

EditGroups
----------

.. currentmodule:: wikibaseintegrator.wbi_editgroups

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~EditGroup
