from __future__ import annotations

import logging
import re
from copy import copy
from typing import TYPE_CHECKING, Any

from entityshape import EntityShape, Result

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models.claims import Claim, Claims
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
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
    def claims(self, value: Claims):
        if not isinstance(value, Claims):
            raise TypeError
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
    def _get(self, entity_id: str, login: _Login | None = None, allow_anonymous: bool = True, is_bot: bool | None = None, **kwargs: Any) -> dict:  # pylint: disable=no-self-use
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

    def _write(self, data: dict | None = None, summary: str | None = None, login: _Login | None = None, allow_anonymous: bool = False, limit_claims: list[str | int] | None = None,
               clear: bool = False, as_new: bool = False, is_bot: bool | None = None, **kwargs: Any) -> dict[str, Any]:
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
        :param kwargs: More arguments for Python requests
        :return: A dictionary representation of the edited Entity
        """

        data = data or {}

        if limit_claims:
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
            data['id'] = None
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

    def write_required(self, base_filter: list[BaseDataType | list[BaseDataType]] | None = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL,
                       **kwargs: Any) -> bool:
        fastrun_container = wbi_fastrun.get_fastrun_container(base_filter=base_filter, **kwargs)

        if base_filter is None:
            base_filter = []

        claims_to_check = []
        for claim in self.claims:
            if claim.mainsnak.property_number in base_filter:
                claims_to_check.append(claim)

        # TODO: Add check_language_data

        return fastrun_container.write_required(data=claims_to_check, cqid=self.id, action_if_exists=action_if_exists)

    def get_entity_url(self, wikibase_url: str | None = None) -> str:
        from wikibaseintegrator.wbi_config import config
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])
        if wikibase_url and self.id:
            return wikibase_url + '/entity/' + self.id

        raise ValueError('wikibase_url or entity ID is null.')

    def schema_validator(self, entity_schema_id: str, language: str | None = None) -> Result:
        if isinstance(entity_schema_id, str):
            pattern = re.compile(r'^(?:[a-zA-Z]+:)?E?([0-9]+)$')
            matches = pattern.match(entity_schema_id)

            if not matches:
                raise ValueError(f"Invalid EntitySchema ID ({entity_schema_id}), format must be 'E[0-9]+'")

            entity_schema_id = f'E{matches.group(1)}'
        elif isinstance(entity_schema_id, int):
            entity_schema_id = f'E{entity_schema_id}'
        else:
            raise ValueError(f"Invalid EntitySchema ID ({entity_schema_id}), format must be 'E[0-9]+'")

        language = str(language or config['DEFAULT_LANGUAGE'])
        return EntityShape(qid=self.id, eid=entity_schema_id, lang=language).get_result()

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
