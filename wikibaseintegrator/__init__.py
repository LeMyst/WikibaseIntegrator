import pkg_resources

from .wikibaseintegrator import WikibaseIntegrator

try:
    __version__ = pkg_resources.get_distribution('wikibaseintegrator').version
except pkg_resources.DistributionNotFound as e:  # pragma: no cover
    __version__ = 'dev'
