.. _index:

WikibaseIntegrator
==================

**WikibaseIntegrator** is a Python library to read and write the data of a Wikibase instance, like
`Wikidata <https://www.wikidata.org/>`_: items, properties, lexemes and MediaInfo entities, with their labels, claims,
qualifiers and references, through the MediaWiki API and the SPARQL endpoint.

.. code-block:: bash

   python -m pip install wikibaseintegrator

.. code-block:: python

   from wikibaseintegrator import WikibaseIntegrator
   from wikibaseintegrator.wbi_config import config

   # Wikimedia asks every tool to identify itself
   config['USER_AGENT'] = 'MyTool/1.0 (https://www.wikidata.org/wiki/User:MyUsername)'

   wbi = WikibaseIntegrator()
   item = wbi.item.get('Q582')
   print(item.labels.get('en'))           # Villeurbanne
   print(item.claims.get('P31')[0].mainsnak.datavalue['value']['id'])

To log in, write entities, use another Wikibase instance or the fast run mode, see the usage guides in the
`README on GitHub <https://github.com/LeMyst/WikibaseIntegrator#readme>`_, and the :doc:`API reference <api/index>`.

.. toctree::
   :maxdepth: 2
   :hidden:

   api/index
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
