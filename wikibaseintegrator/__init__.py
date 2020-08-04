import pkg_resources

import wikibaseintegrator.wdi_core
import wikibaseintegrator.wdi_fastrun
import wikibaseintegrator.wdi_helpers
import wikibaseintegrator.wdi_login

try:
    __version__ = pkg_resources.get_distribution("wikibaseintegrator").version
except Exception as e:
    __version__ = ""