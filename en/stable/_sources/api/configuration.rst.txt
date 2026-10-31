Configuration, enums and exceptions
===================================

The global options, the enumerations of the API values, the exceptions, the retries and the EditGroups.

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

   ~MWApiError
   ~ModificationFailed
   ~SaveFailed
   ~NonExistentEntityError
   ~MissingExtensionError
   ~MissingEntityException
   ~EmptyValueError
   ~UnknownDatatypeError
   ~AnonymousEditNotAllowedError
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

EditGroups
----------

.. currentmodule:: wikibaseintegrator.wbi_editgroups

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~EditGroup
