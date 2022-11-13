"""
WikibaseIntegrator Library
~~~~~~~~~~~~~~~~~~~~~

WikibaseIntegrator is a Wikibase library, written in Python, for human beings.
Basic read usage:

   >>> from wikibaseintegrator import WikibaseIntegrator
   >>> from wikibaseintegrator.wbi_config import config
   >>> config['USER_AGENT'] = 'Item Get Notebook'
   >>> wbi = WikibaseIntegrator()
   >>> q42 = wbi.item.get('Q42')
   >>> q42.labels.get('en').value
   'Douglas Adams'

Full documentation is available at <https://wikibaseintegrator.readthedocs.io/>.
"""

from .wikibaseintegrator import WikibaseIntegrator

__version__ = '0.12.2'
