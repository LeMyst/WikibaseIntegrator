from __future__ import annotations

import logging
from copy import copy
from typing import TYPE_CHECKING, Any

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models.aliases import Aliases
from wikibaseintegrator.models.claims import Claim, Claims
from wikibaseintegrator.models.descriptions import Descriptions
from wikibaseintegrator.models.labels import Labels
from wikibaseintegrator.wbi_enums import ActionIfExists, EntityField
from wikibaseintegrator.wbi_exceptions import MissingEntityException
from wikibaseintegrator.wbi_helpers import delete_page, edit_entity, mediawiki_api_call_helper
from wikibaseintegrator.wbi_login import _Login

if TYPE_CHECKING:
    from wikibaseintegrator import WikibaseIntegrator

log = logging.getLogger(__name__)


class BaseEntity:
    ETYPE = 'base-entity'
    subclasses: list[type[BaseEntity]] = []

    def __init__(self, api: WikibaseIntegrator | None = None, title: str | None = None, pageid: int | None = None, lastrevid: int | None = None, type: str | None = None,
                 id: str | None = None, claims: Claims | None = None, is_bot: bool | None = None, login: _Login | None = None):
        if not api:
            from wikibaseintegrator import WikibaseIntegrator
            self.api = WikibaseIntegrator()
        else:
            self.api = copy(api)

        self.api.is_bot = is_bot or self.api.is_bot
        self.api.login = login or self.api.login

        self.title = title
        self.pageid = pageid
        self.lastrevid = lastrevid
        self.type = str(type or self.ETYPE)
        self.id = id
        self.claims = claims or Claims()

    # Allow registration of subclasses of BaseEntity into BaseEntity.subclasses
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

    @property
    def api(self) -> WikibaseIntegrator:
        return self.__api

    @api.setter
    def api(self, value: WikibaseIntegrator):
        from wikibaseintegrator import WikibaseIntegrator
        if not isinstance(value, WikibaseIntegrator):
            raise TypeError
        self.__api = value

    @property
    def title(self) -> str | None:
        return self.__title

    @title.setter
    def title(self, value: str | None):
        self.__title = value

    @property
    def pageid(self) -> str | int | None:
        return self.__pageid

    @pageid.setter
    def pageid(self, value: str | int | None):
        if isinstance(value, str):
            self.__pageid: str | int | None = int(value)
        else:
            self.__pageid = value

    @property
    def lastrevid(self) -> int | None:
        return self.__lastrevid

    @lastrevid.setter
    def lastrevid(self, value: int | None):
        self.__lastrevid = value

    @property
    def type(self) -> str:
        return self.__type

    @type.setter
    def type(self, value: str):
        self.__type = value

    @property
    def id(self) -> str | None:
        return self.__id

    @id.setter
    def id(self, value: str | None):
        self.__id = value

    @property
    def claims(self) -> Claims:
        return self.__claims

    @claims.setter
    def claims(self, value: Claim | Claims):
        if not isinstance(value, Claims) and not isinstance(value, Claim):
            raise TypeError

        if isinstance(value, Claim):
            value = Claims().add(claims=value)

        self.__claims = value

    def add_claims(self, claims: Claim | list[Claim] | Claims, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> BaseEntity:
        """

        :param claims: A Claim, list of Claim or just a Claims object to add to this Claims object.
        :param action_if_exists: Replace or append the statement. You can force an addition if the declaration already exists.
            KEEP: The original claim will be kept and the new one will not be added (because there is already one with this property number)
            APPEND_OR_REPLACE: The new claim will be added only if the new one is different (by comparing values)
            FORCE_APPEND: The new claim will be added even if already exists
            REPLACE_ALL: The new claim will replace the old one
        :return: Return the updated entity object.
        """

        self.claims.add(claims=claims, action_if_exists=action_if_exists)

        return self

    def get_json(self) -> dict[str, str | dict[str, list]]:
        """
        To get the dict equivalent of the JSON representation of the entity.

        :return:
        """
        json_data: dict = {
            'type': self.type,
            'claims': self.claims.get_json()
        }
        if self.id:
            json_data['id'] = self.id

        return json_data

    def from_json(self, json_data: dict[str, Any]) -> BaseEntity:
        """
        Import a dictionary into BaseEntity attributes.

        :param json_data: A specific dictionary from MediaWiki API
        :return:
        """
        if 'missing' in json_data:  # TODO: 1.35 compatibility
            raise MissingEntityException('The MW API returned that the entity was missing.')

        if 'title' in json_data:  # TODO: 1.35 compatibility
            self.title = str(json_data['title'])
        if 'pageid' in json_data:  # TODO: 1.35 compatibility
            self.pageid = int(json_data['pageid'])
        self.lastrevid = int(json_data['lastrevid'])
        self.type = str(json_data['type'])
        self.id = str(json_data['id'])
        if 'claims' in json_data:  # 'claims' is named 'statements' in Wikimedia Commons MediaInfo
            self.claims = Claims().from_json(json_data['claims'])

        return self

    # noinspection PyMethodMayBeStatic
    def _get(self, entity_id: str, login: _Login | None = None, allow_anonymous: bool = True, is_bot: bool | None = None, props: str | list | None = None, **kwargs: Any) -> dict:  # pylint: disable=no-self-use
        """
        Retrieve an entity in json representation from the Wikibase instance

        :param entity_id: The ID of the entity to retrieve
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: python complex dictionary representation of a json
        """

        params = {
            'action': 'wbgetentities',
            'ids': entity_id,
            'format': 'json'
        }

        if props:
            if isinstance(props, list):
                props = '|'.join(props)
            params['props'] = props

            if 'info' not in props:
                params['props'] += '|info'

        login = login or self.api.login
        is_bot = is_bot if is_bot is not None else self.api.is_bot

        return mediawiki_api_call_helper(data=params, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)

    def clear(self, **kwargs: Any) -> dict[str, Any]:
        """
        Use the `clear` parameter of `wbeditentity` API call to clear the content of the entity.
        The entity will be updated with an empty dictionary.

        :param kwargs: More arguments for _write() and Python requests
        :return: A dictionary representation of the edited Entity
        """
        return self._write(data={}, clear=True, **kwargs)

    def get_claims(self, property: str, login: _Login | None = None, allow_anonymous: bool = True, is_bot: bool | None = None, **kwargs: Any):
        params = {
            'action': 'wbgetclaims',
            'entity': self.id,
            'property': property,
            'format': 'json'
        }

        login = login or self.api.login
        is_bot = is_bot if is_bot is not None else self.api.is_bot

        json_data = mediawiki_api_call_helper(data=params, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)
        self.claims.from_json(json_data['claims'])
        return self

    def _write(self, data: dict | None = None, summary: str | None = None, login: _Login | None = None, allow_anonymous: bool = False, limit_claims: list[str | int] | None = None,
               clear: bool = False, as_new: bool = False, is_bot: bool | None = None, fields_to_update: list | None | EntityField = None, **kwargs: Any) -> dict[str, Any]:
        """
        Writes the entity JSON to the Wikibase instance and after successful write, returns the "entity" part of the response.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param limit_claims: Limit to a list of specific claims to reduce the data sent and avoid sending the complete entity.
        :param clear: If set, the complete entity is emptied before proceeding. The entity will not be saved before it is filled with the "data", possibly with parts excluded.
        :param as_new: Write the entity as a new one
        :param is_bot: Add the bot flag to the query
        :param field_to_update: A list or a single EntityField to update. If not set, all fields will be updated.
        :param kwargs: More arguments for Python requests
        :return: A dictionary representation of the edited Entity
        """

        data = data or {}

        if fields_to_update is not None:
            if not isinstance(fields_to_update, list):
                fields_to_update = [fields_to_update]

            if EntityField.ALIASES not in fields_to_update and 'aliases' in data:
                del data['aliases']

            if EntityField.CLAIMS not in fields_to_update and 'claims' in data:
                del data['claims']

            if EntityField.DESCRIPTIONS not in fields_to_update and 'descriptions' in data:
                del data['descriptions']

            if EntityField.LABELS not in fields_to_update and 'labels' in data:
                del data['labels']

            if EntityField.SITELINKS not in fields_to_update and 'sitelinks' in data:
                del data['sitelinks']

            # Lexeme-specific fields
            if EntityField.LEMMAS not in fields_to_update and 'lemmas' in data:
                del data['lemmas']

            if EntityField.LEXICAL_CATEGORY not in fields_to_update and 'lexicalCategory' in data:
                del data['lexicalCategory']

            if EntityField.LANGUAGE not in fields_to_update and 'language' in data:
                del data['language']

            if EntityField.FORMS not in fields_to_update and 'forms' in data:
                del data['forms']

            if EntityField.SENSES not in fields_to_update and 'senses' in data:
                del data['senses']

        if limit_claims and 'claims' in data:
            new_claims = {}

            if not isinstance(limit_claims, list):
                limit_claims = [limit_claims]

            for claim in limit_claims:
                if isinstance(claim, int):
                    claim = 'P' + str(claim)

                if claim in data['claims']:
                    new_claims[claim] = data['claims'][claim]

            data['claims'] = new_claims

        is_bot = is_bot if is_bot is not None else self.api.is_bot
        login = login or self.api.login

        if as_new:
            entity_id = None
            # Don't keep an id when creating a new entity: a null id in the data payload is rejected by the API.
            data.pop('id', None)
        else:
            entity_id = self.id

        try:
            json_result: dict = edit_entity(data=data, id=entity_id, type=self.type, summary=summary, clear=clear, is_bot=is_bot, allow_anonymous=allow_anonymous,
                                            login=login, **kwargs)
        except Exception:
            log.exception('Error while writing to the Wikibase instance')
            raise

        return json_result['entity']

    def delete(self, login: _Login | None = None, allow_anonymous: bool = False, is_bot: bool | None = None, **kwargs: Any):
        """
        Delete the current entity. Use the pageid first if available and fallback to the page title.

        :param login: A wbi_login.Login instance
        :param allow_anonymous: Allow an unidentified edit to the MediaWiki API (default False)
        :param is_bot: Flag the edit as a bot
        :param reason: Reason for the deletion. If not set, an automatically generated reason will be used.
        :param deletetalk: Delete the talk page, if it exists.
        :param kwargs: Any additional keyword arguments to pass to mediawiki_api_call_helper and requests.request
        :return: The data returned by the API as a dictionary
        """

        login = login or self.api.login

        if not self.pageid and not self.title:
            raise ValueError("A pageid or a page title attribute must be set before deleting an entity object.")

        # If there is no pageid, fallback to using the page title. It's not the preferred method.
        if not self.pageid:
            return delete_page(title=self.title, pageid=None, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)
        else:
            if not isinstance(self.pageid, int):
                raise ValueError(f"The entity must have a pageid attribute correctly set ({self.pageid})")

            return delete_page(title=None, pageid=self.pageid, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)

    def write_required(self, base_filter: list[BaseDataType | list[BaseDataType]], action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL, **kwargs: Any) -> bool:
        fastrun_container = wbi_fastrun.get_fastrun_container(base_filter=base_filter, **kwargs)

        # Collect the property numbers targeted by the base_filter. It supports both the simple form (a
        # BaseDataType) and the property-path form (a list of two BaseDataType), whose anchor is the first property.
        base_filter_props = set()
        for prop in base_filter:
            if isinstance(prop, BaseDataType):
                base_filter_props.add(prop.mainsnak.property_number)
            elif isinstance(prop, list) and prop and isinstance(prop[0], BaseDataType):
                base_filter_props.add(prop[0].mainsnak.property_number)

        pfilter: set = set()
        for claim in self.claims:
            if claim.mainsnak.property_number in base_filter_props:
                pfilter.add(claim.mainsnak.property_number)

        property_filter: list[str] = list(pfilter)

        # TODO: Add check_language_data

        # Restrict the check to the entity being edited, when it already has an ID
        entity_filter = [self.id] if self.id else None

        return fastrun_container.write_required(claims=self.claims, entity_filter=entity_filter, property_filter=property_filter, action_if_exists=action_if_exists)

    def get_entity_url(self, wikibase_url: str | None = None) -> str:
        from wikibaseintegrator.wbi_config import config
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])
        if wikibase_url and self.id:
            return wikibase_url + '/entity/' + self.id

        raise ValueError('wikibase_url or entity ID is null')

    def download_entity_ttl(self, **kwargs) -> str:
        from wikibaseintegrator.wbi_helpers import download_entity_ttl
        if self.id:
            return download_entity_ttl(self.id, **kwargs)

        raise ValueError('entity ID is null')

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class TermsEntity(BaseEntity):
    """
    Base class for the entities that share the labels/descriptions/aliases "terms": Item, Property and MediaInfo.
    """

    def __init__(self, labels: Labels | None = None, descriptions: Descriptions | None = None, aliases: Aliases | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.labels = labels or Labels()
        self.descriptions = descriptions or Descriptions()
        self.aliases = aliases or Aliases()

    @property
    def labels(self) -> Labels:
        return self.__labels

    @labels.setter
    def labels(self, labels: Labels):
        if not isinstance(labels, Labels):
            raise TypeError
        self.__labels = labels

    @property
    def descriptions(self) -> Descriptions:
        return self.__descriptions

    @descriptions.setter
    def descriptions(self, descriptions: Descriptions):
        if not isinstance(descriptions, Descriptions):
            raise TypeError
        self.__descriptions = descriptions

    @property
    def aliases(self) -> Aliases:
        return self.__aliases

    @aliases.setter
    def aliases(self, aliases: Aliases):
        if not isinstance(aliases, Aliases):
            raise TypeError
        self.__aliases = aliases

    def _terms_from_json(self, json_data: dict[str, Any]) -> None:
        """
        Deserialize the labels/descriptions/aliases blocks.

        Only the terms present in ``json_data`` are set, so this is safe to call on entities that never carry some
        of them (e.g. a MediaInfo entity usually has no aliases).
        """
        if 'labels' in json_data:
            self.labels = Labels().from_json(json_data['labels'])
        if 'descriptions' in json_data:
            self.descriptions = Descriptions().from_json(json_data['descriptions'])
        if 'aliases' in json_data:
            self.aliases = Aliases().from_json(json_data['aliases'])
