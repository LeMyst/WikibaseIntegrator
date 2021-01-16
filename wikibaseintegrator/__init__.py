import pkg_resources

import wikibaseintegrator.wbi_core
import wikibaseintegrator.wbi_fastrun
import wikibaseintegrator.wbi_login

try:
    __version__ = pkg_resources.get_distribution("wikibaseintegrator").version
except Exception as e:
    __version__ = ""
