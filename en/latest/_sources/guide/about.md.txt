# About

## WikibaseIntegrator / WikidataIntegrator

WikibaseIntegrator (wbi) is a fork of [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) (wdi) whose
purpose is to focus on an improved compatibility with Wikibase and adding missing functionalities.
The main differences between these two libraries are :

* A complete rewrite of the library with a more object-oriented architecture allowing for easy interaction, data
  validation and extended functionality
* Add support for reading and writing Lexeme, MediaInfo and Property entities
* Python 3.11 to 3.15 support, validated with unit tests
* Type hints implementation for arguments and return, checked with mypy static type checker
* Add OAuth 2.0 login method
* Add logging module support

WikibaseIntegrator also provides a "fast run" mode, which compares the local data with the live data through the SPARQL
endpoint and only writes to the Wikibase instance when something actually changed (see
[Examples (in "fast run" mode)](fastrun.md)).

To port a WikidataIntegrator script, see [Migrating from WikidataIntegrator](wikidataintegrator.md).

## Citing WikibaseIntegrator

Every release is archived on [Zenodo](https://doi.org/10.5281/zenodo.5594623). To cite WikibaseIntegrator, use the
DOI [10.5281/zenodo.5594623](https://doi.org/10.5281/zenodo.5594623), which always resolves to the latest archived
version, or the DOI of the version you used, listed on the Zenodo page. The "Cite this repository" button of the
[GitHub repository](https://github.com/LeMyst/WikibaseIntegrator) gives the citation in the APA and BibTeX formats,
from the [CITATION.cff](https://github.com/LeMyst/WikibaseIntegrator/blob/master/CITATION.cff) file.

## Other projects

Here is a list of different projects that use the library:

* https://github.com/ACMILabs/acmi-wikidata-bot - A synchronisation robot to push ACMI API Wikidata links to Wikidata.
* https://github.com/LeMyst/wd-population - Update French population on Wikidata
* https://github.com/SisonkeBiotik-Africa/AfriBioML - Resources for developing a bibliometric study on machine learning for healthcare in Africa
* https://github.com/SisonkeBiotik-Africa/Relational-NER - A Python code for enhancing the output of multilingual named entity recognition based on Wikidata relations
* https://github.com/SoftwareUnderstanding/SALTbot - Software and Article Linker Toolbot
* https://github.com/dpriskorn/ItemSubjector - CLI-tool to easily add "main subject" aka topics in bulk to groups of items on Wikidata
* https://github.com/dpriskorn/hiking_trail_matcher - Script that helps link together hiking trails in Wikidata and OpenStreetMap
* https://github.com/eoan-ermine/wikidata_statistik_population - Update German population on Wikidata
* https://github.com/internetarchive/cgraphbot - Wikibase bot for updating identifiers and citation relationships
* https://github.com/lubianat/ibge_2021_to_wikidata - Update Population of Brazilian Cities
* https://github.com/lcnetdev/lccn-wikidata-bot - Adding LCCNs (Library of Congress Control Number) from NACO (Name Authority Cooperative Program) to Wikidata
* https://github.com/dpriskorn/WikidataEurLexScraper - Improve all Eur-Lex items in Wikidata based on information scraped from Eur-Lex
* https://github.com/dpriskorn/LexDanNet - Help link DanNet 2.2 word ID with Danish Wikidata lexemes
* https://github.com/lubianat/kudos_wikibase
* https://github.com/dlindem/wikibase
