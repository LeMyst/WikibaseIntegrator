"""
Support of the WikibaseManifest extension (https://www.mediawiki.org/wiki/Extension:WikibaseManifest), which describes a
Wikibase instance for the tools: its API endpoints, query service, RDF namespaces, entity types and the local IDs of
some Wikidata entities. It is installed on the instances of Wikibase.cloud, for example.

Configure WikibaseIntegrator for an instance from its manifest::

    from wikibaseintegrator import wbi_manifest

    manifest = wbi_manifest.get_manifest('https://wikibase.world/w/rest.php')
    manifest.apply()  # sets wbi_config['MEDIAWIKI_API_URL'], ['SPARQL_ENDPOINT_URL'], ['WIKIBASE_URL']...

    instance_of = manifest.local_id('P31')  # the local property equivalent to P31 on Wikidata, e.g. 'P3'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_exceptions import MissingExtensionError
from wikibaseintegrator.wbi_helpers import _get_default_session, get_user_agent

#: The path of the manifest, relative to the MediaWiki REST API (rest.php)
MANIFEST_PATH = '/wikibase-manifest/v0/manifest'

#: The key of the Wikidata mappings in equiv_entities, the only hub the format defines
WIKIDATA = 'wikidata.org'


@dataclass
class WikibaseManifest:
    """
    The manifest of a Wikibase instance, as returned by get_manifest(). The optional parts of the format are omitted by
    the instances which don't have them (e.g. no query service): their attribute is then None or empty.
    """
    #: The name of the instance, e.g. 'Wikibase World'
    name: str
    #: The URL of the MediaWiki scripts (index.php, api.php...), e.g. 'https://wikibase.world/w'
    root_script_url: str
    #: The URL of the main page
    main_page_url: str
    #: The MediaWiki Action API (api.php)
    mediawiki_api_url: str
    #: The MediaWiki REST API (rest.php)
    mediawiki_rest_url: str
    #: The maxlag recommended by the administrators, in seconds
    max_lag: int | None = None
    #: The SPARQL endpoint of the Wikibase query service, if any
    sparql_endpoint_url: str | None = None
    #: The external services: queryservice, queryservice_ui, quickstatements, openrefine_reconcile...
    external_services: dict[str, str] = field(default_factory=dict)
    #: The local IDs of entities of other Wikibase instances, e.g. {'wikidata.org': {'properties': {'P31': 'P1'}}}
    equiv_entities: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    #: The RDF namespaces of the instance, by prefix ('' for the entities, 'p', 'ps', 'wdt'...)
    local_rdf_namespaces: dict[str, str] = field(default_factory=dict)
    #: The entity types of the instance and their namespace, e.g. {'item': {'namespace_id': 120, 'namespace_name': 'Item'}}
    local_entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: The page to register an OAuth consumer, if the OAuth extension is installed
    oauth_registration_page: str | None = None
    #: The manifest, as returned by the instance
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> WikibaseManifest:
        """
        Build the manifest from the JSON returned by the instance.

        :param json_data: The decoded JSON of the manifest
        :return: The manifest
        """
        external_services = dict(json_data.get('external_services') or {})
        return cls(
            name=json_data['name'],
            root_script_url=json_data['root_script_url'],
            main_page_url=json_data['main_page_url'],
            mediawiki_api_url=json_data['api']['action'],
            mediawiki_rest_url=json_data['api']['rest'],
            max_lag=json_data.get('max_lag'),
            sparql_endpoint_url=external_services.get('queryservice'),
            external_services=external_services,
            equiv_entities=dict(json_data.get('equiv_entities') or {}),
            local_rdf_namespaces=dict(json_data.get('local_rdf_namespaces') or {}),
            local_entities=dict(json_data.get('local_entities') or {}),
            oauth_registration_page=(json_data.get('oauth') or {}).get('registration_page'),
            raw=json_data,
        )

    @property
    def mediawiki_index_url(self) -> str:
        """The index.php of the instance."""
        return self.root_script_url.rstrip('/') + '/index.php'

    @property
    def wikibase_url(self) -> str | None:
        """
        The Wikibase URL, as wbi_config['WIKIBASE_URL'] expects it: the concept URI of the entities without '/entity/',
        e.g. 'https://wikibase.world' for 'https://wikibase.world/entity/'. None if the concept namespace
        doesn't end with '/entity/'.
        """
        concept_uri = self.local_rdf_namespaces.get('')
        if concept_uri is None or not concept_uri.endswith('/entity/'):
            return None
        return concept_uri[:-len('/entity/')]

    def local_id(self, entity_id: str, hub: str = WIKIDATA) -> str | None:
        """
        The local ID of an entity of another Wikibase instance, from the equivalences of the manifest.

        :param entity_id: The ID on the other instance, e.g. 'P31'
        :param hub: The other instance, as named by the manifest. Wikidata by default, the only one of the format.
        :return: The local ID, e.g. 'P3', or None without a known equivalent
        """
        for entities in self.equiv_entities.get(hub, {}).values():
            if entity_id in entities:
                return entities[entity_id]
        return None

    def config(self) -> dict[str, str]:
        """
        The wbi_config values to use this instance: MEDIAWIKI_API_URL, MEDIAWIKI_REST_URL, MEDIAWIKI_INDEX_URL,
        WIKIBASE_URL and SPARQL_ENDPOINT_URL. The last two are left out when the manifest doesn't give them.
        """
        values = {
            'MEDIAWIKI_API_URL': self.mediawiki_api_url,
            'MEDIAWIKI_REST_URL': self.mediawiki_rest_url,
            'MEDIAWIKI_INDEX_URL': self.mediawiki_index_url,
        }
        if self.wikibase_url is not None:
            values['WIKIBASE_URL'] = self.wikibase_url
        if self.sparql_endpoint_url is not None:
            values['SPARQL_ENDPOINT_URL'] = self.sparql_endpoint_url
        return values

    def apply(self, target: dict[str, Any] | None = None) -> None:
        """
        Set the wbi_config values of this instance (see config()), the other options are kept.

        :param target: The configuration to update. wbi_config by default.
        """
        (config if target is None else target).update(self.config())


def manifest_url(url: str | None = None) -> str:
    """
    The URL of the manifest, from the MediaWiki REST API of the instance (rest.php) or the URL of the manifest itself.

    :param url: The REST API URL (e.g. 'https://wikibase.world/w/rest.php') or the manifest URL. Use
        wbi_config['MEDIAWIKI_REST_URL'] by default.
    :return: The URL of the manifest
    """
    url = str(url or config['MEDIAWIKI_REST_URL']).rstrip('/')
    if url.endswith(MANIFEST_PATH):
        return url
    return url + MANIFEST_PATH


def get_manifest(url: str | None = None, user_agent: str | None = None) -> WikibaseManifest:
    """
    Download the manifest of a Wikibase instance with the WikibaseManifest extension.

    :param url: The MediaWiki REST API of the instance (e.g. 'https://wikibase.world/w/rest.php') or the URL of the
        manifest. Use wbi_config['MEDIAWIKI_REST_URL'] by default.
    :param user_agent: The user agent string used in the HTTP request headers. Default: config['USER_AGENT'], if set
    :return: The manifest
    :raises MissingExtensionError: If the instance doesn't have the WikibaseManifest extension.
    :raises requests.HTTPError: If the request fails for another reason.
    """
    user_agent = user_agent or (str(config['USER_AGENT']) if config['USER_AGENT'] is not None else None)

    response = _get_default_session().get(manifest_url(url), headers={'User-Agent': get_user_agent(user_agent), 'Accept': 'application/json'}, timeout=config['TIMEOUT'])
    if response.status_code == 404:
        # The REST API answers rest-no-match for a path that no extension handles
        try:
            error = response.json()
        except requests.exceptions.JSONDecodeError:
            error = {}
        info = (error.get('messageTranslations') or {}).get('en') or error.get('message') or response.reason
        raise MissingExtensionError({'code': error.get('errorKey', 'rest-no-match'), 'info': info}, extension='WikibaseManifest', response=error)
    response.raise_for_status()

    return WikibaseManifest.from_json(response.json())
