from __future__ import annotations

import logging
from copy import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import ujson

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models.claims import Claim, Claims
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_exceptions import MWApiError, NonExistentEntityError, NonUniqueLabelDescriptionPairError
from wikibaseintegrator.wbi_helpers import delete_page, mediawiki_api_call_helper
from wikibaseintegrator.wbi_login import _Login

if TYPE_CHECKING:
    from wikibaseintegrator import WikibaseIntegrator

log = logging.getLogger(__name__)


class BaseEntity:
    ETYPE = 'base-entity'

    def __init__(self, api: 'WikibaseIntegrator' = None, title: str = None, pageid: int = None, lastrevid: int = None, type: str = None, id: str = None, claims: Claims = None,
                 is_bot: bool = None, login: _Login = None):
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

    @property
    def api(self) -> WikibaseIntegrator:
        return self.__api

    @api.setter
    def api(self, value: WikibaseIntegrator):
        self.__api = value

    @property
    def title(self) -> Optional[str]:
        return self.__title

    @title.setter
    def title(self, value: Optional[str]):
        self.__title = value

    @property
    def pageid(self) -> Optional[int]:
        return self.__pageid

    @pageid.setter
    def pageid(self, value: Optional[int]):
        self.__pageid = value

    @property
    def lastrevid(self) -> Optional[int]:
        return self.__lastrevid

    @lastrevid.setter
    def lastrevid(self, value: Optional[int]):
        self.__lastrevid = value

    @property
    def type(self) -> str:
        return self.__type

    @type.setter
    def type(self, value: str):
        self.__type = value

    @property
    def id(self) -> Optional[str]:
        return self.__id

    @id.setter
    def id(self, value: Optional[str]):
        self.__id = value

    @property
    def claims(self) -> Claims:
        return self.__claims

    @claims.setter
    def claims(self, value: Claims):
        self.__claims = value

    def add_claims(self, claims: Union[Claim, List], action_if_exists: ActionIfExists = ActionIfExists.APPEND) -> BaseEntity:
        if isinstance(claims, Claim):
            claims = [claims]
        elif not isinstance(claims, list):
            raise TypeError()

        self.claims.add(claims=claims, action_if_exists=action_if_exists)

        return self

    def get_json(self) -> Dict[str, Union[str, Dict[str, List]]]:
        """
        To get the dict equivalent of the JSON representation of the entity.

        :return:
        """
        json_data: Dict = {
            'type': self.type,
            'claims': self.claims.get_json()
        }
        if self.id:
            json_data['id'] = self.id

        return json_data

    def from_json(self, json_data: Dict[str, Any]) -> BaseEntity:
        """
        Import a dictionary into BaseEntity attributes.

        :param json_data: A specific dictionary from MediaWiki API
        :return:
        """
        if 'missing' in json_data:  # TODO: 1.35 compatibility
            raise NonExistentEntityError('The MW API returned that the entity was missing.')

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
    def _get(self, entity_id: str, login: _Login = None, allow_anonymous: bool = True, is_bot: bool = None, **kwargs: Any) -> Dict:  # pylint: disable=no-self-use
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

    def clear(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Use the `clear` parameter of `wbeditentity` API call to clear the content of the entity.
        The entity will be updated with an empty dictionary.

        :param kwargs: More arguments for _write() and Python requests
        :return: A dictionary representation of the edited Entity
        """
        return self._write(data={}, clear=True, **kwargs)

    def _write(self, data: Dict = None, summary: str = None, login: _Login = None, allow_anonymous: bool = False, clear: bool = False, is_bot: bool = None, **kwargs: Any) -> Dict[
        str, Any]:
        """
        Writes the entity JSON to the Wikibase instance and after successful write, returns the "entity" part of the response.

        :param data: The serialized object that is used as the data source. A newly created entity will be assigned an 'id'.
        :param summary: A summary of the edit
        :param login: A login instance
        :param allow_anonymous: Force a check if the query can be anonymous or not
        :param clear: If set, the complete entity is emptied before proceeding. The entity will not be saved before it is filled with the "data", possibly with parts excluded.
        :param is_bot: Add the bot flag to the query
        :param kwargs: More arguments for Python requests
        :return: A dictionary representation of the edited Entity
        """

        data = data or {}

        # if all_claims:
        #     data = json.JSONEncoder().encode(self.json_representation)
        # else:
        #     new_json_repr = {k: self.json_representation[k] for k in set(list(self.json_representation.keys())) - {'claims'}}
        #     new_json_repr['claims'] = {}
        #     for claim in self.json_representation['claims']:
        #         if [True for x in self.json_representation['claims'][claim] if 'id' not in x or 'remove' in x]:
        #             new_json_repr['claims'][claim] = copy.deepcopy(self.json_representation['claims'][claim])
        #             for statement in new_json_repr['claims'][claim]:
        #                 if 'id' in statement and 'remove' not in statement:
        #                     new_json_repr['claims'][claim].remove(statement)
        #             if not new_json_repr['claims'][claim]:
        #                 new_json_repr['claims'].pop(claim)
        #     data = json.JSONEncoder().encode(new_json_repr)

        payload: Dict[str, Any] = {
            'action': 'wbeditentity',
            'data': ujson.dumps(data),
            'format': 'json',
            'summary': summary
        }

        if not summary:
            payload.pop('summary')

        is_bot = is_bot if is_bot is not None else self.api.is_bot
        if is_bot:
            payload.update({'bot': ''})

        if clear:
            payload.update({'clear': True})

        if self.id:
            payload.update({'id': self.id})
        else:
            payload.update({'new': self.type})

        if self.lastrevid:
            payload.update({'baserevid': self.lastrevid})

        login = login or self.api.login

        try:
            json_result: dict = mediawiki_api_call_helper(data=payload, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)
        except Exception:
            logging.error('Error while writing to the Wikibase instance')
            raise
        else:
            if 'error' in json_result and 'messages' in json_result['error']:
                error_msg_names = {x.get('name') for x in json_result['error']['messages']}
                if 'wikibase-validator-label-with-description-conflict' in error_msg_names:
                    raise NonUniqueLabelDescriptionPairError(json_result)

            if 'error' in json_result:
                raise MWApiError(json_result)

        return json_result['entity']

    def delete(self, login: _Login = None, allow_anonymous: bool = False, is_bot: bool = None, **kwargs: Any):
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

        if not self.pageid and not self.title:
            raise ValueError("A pageid or a page title attribute must be set before deleting an entity object.")

        # If there is no pageid, fallback to using the page title. It's not the preferred method.
        if not self.pageid:
            return delete_page(title=self.title, pageid=None, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)
        else:
            if isinstance(self.pageid, int):
                raise ValueError("The entity must have a pageid attribute correctly set")

            return delete_page(title=None, pageid=self.pageid, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs)

    def write_required(self, base_filter: List[BaseDataType | List[BaseDataType]] = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE, **kwargs: Any) -> bool:
        fastrun_container = wbi_fastrun.get_fastrun_container(base_filter=base_filter, **kwargs)

        if base_filter is None:
            base_filter = []

        claims_to_check = []
        for claim in self.claims:
            if claim.mainsnak.property_number in base_filter:
                claims_to_check.append(claim)

        # TODO: Add check_language_data

        return fastrun_container.write_required(data=claims_to_check, cqid=self.id, action_if_exists=action_if_exists)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
