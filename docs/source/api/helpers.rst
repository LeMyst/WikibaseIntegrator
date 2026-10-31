Helpers
=======

Functions calling the MediaWiki and Wikibase APIs directly. Import them from ``wikibaseintegrator.wbi_helpers``.

API calls
---------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~mediawiki_api_call_helper
   ~mediawiki_api_call
   ~edit_entity

Search and queries
------------------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~search_entities
   ~fulltext_search
   ~generate_entity_instances
   ~execute_sparql_query

Edits
-----

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~merge_items
   ~merge_multiple_items
   ~merge_lexemes
   ~create_redirect
   ~set_claim
   ~remove_claims
   ~delete_page

Lexemes
-------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~lexeme_add_form
   ~lexeme_edit_form
   ~lexeme_remove_form
   ~lexeme_add_sense
   ~lexeme_edit_sense
   ~lexeme_remove_sense

Values
------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~parse_value
   ~format_amount
   ~get_available_badges
   ~check_constraints

Wikibase instance
-----------------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~check_wikibase
   ~WikibaseCheck
   ~get_user_agent
   ~download_entity_ttl

Experimental
------------

.. currentmodule:: wikibaseintegrator.wbi_helpers

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~format2wbi
