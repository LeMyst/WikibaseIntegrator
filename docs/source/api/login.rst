Login
=====

The login methods, passed to ``WikibaseIntegrator(login=...)``. Import them from ``wikibaseintegrator.wbi_login``. They all derive from
:class:`~wikibaseintegrator.wbi_login.BaseLogin`, the type of the ``login`` parameters of the library.

.. currentmodule:: wikibaseintegrator.wbi_login

.. autosummary::
   :toctree: generated
   :nosignatures:
   :template: autosummary/class-inherited.rst

   ~OAuth2
   ~OAuth1
   ~Login
   ~Clientlogin

Other
-----

.. currentmodule:: wikibaseintegrator.wbi_login

.. autosummary::
   :toctree: generated
   :nosignatures:

   ~WCQSAuth
   ~LoginError
