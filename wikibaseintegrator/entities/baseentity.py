from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import simplejson

from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models.claims import Claim, Claims
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_exceptions import MWApiError, NonUniqueLabelDescriptionPairError
from wikibaseintegrator.wbi_fastrun import FastRunContainer
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper
from wikibaseintegrator.wbi_login import Login

if TYPE_CHECKING:
    from wikibaseintegrator import WikibaseIntegrator


class BaseEntity:
    fast_run_store: List[FastRunContainer] = []

    ETYPE = 'base-entity'

    def __init__(self, api: 'WikibaseIntegrator' = None, lastrevid: int = None, type: str = None, id: str = None, claims: Claims = None, is_bot: bool = None, login: Login = None):
        if not api:
            from wikibaseintegrator import WikibaseIntegrator
            self.api = WikibaseIntegrator()
        else:
            self.api = copy(api)

        self.api.is_bot = is_bot or self.api.is_bot
        self.api.login = login or self.api.login

        self.lastrevid = lastrevid
        self.type = str(type or self.ETYPE)
        self.id = id
        self.claims = claims or Claims()

        self.fast_run_container: Optional[FastRunContainer] = None

        self.debug = config['DEBUG']

    def add_claims(self, claims: Union[Claim, list], action_if_exists: ActionIfExists = ActionIfExists.APPEND) -> BaseEntity:
        if isinstance(claims, Claim):
            claims = [claims]
        elif not isinstance(claims, list):
            raise TypeError()

        self.claims.add(claims=claims, action_if_exists=action_if_exists)

        return self

    def get_json(self) -> Dict[str, Union[str, Dict[str, list]]]:
        json_data: Dict = {
            'type': self.type,
            'claims': self.claims.get_json()
        }
        if self.id:
            json_data['id'] = self.id
        if self.type == 'mediainfo':  # MediaInfo change name of 'claims' to 'statements'
            json_data['statements'] = json_data.pop('claims')

        return json_data

    def from_json(self, json_data: Dict[str, Any]) -> BaseEntity:
        if 'missing' in json_data:
            raise ValueError('Entity is nonexistent')

        self.lastrevid = int(json_data['lastrevid'])
        self.type = str(json_data['type'])
        self.id = str(json_data['id'])
        if self.type == 'mediainfo':  # 'claims' is named 'statements' in Wikimedia Commons MediaInfo
            self.claims = Claims().from_json(json_data['statements'])
        else:
            self.claims = Claims().from_json(json_data['claims'])

        return self

    # noinspection PyMethodMayBeStatic
    def _get(self, entity_id: str, **kwargs) -> Dict:
        """
        retrieve an item in json representation from the Wikibase instance

        :return: python complex dictionary representation of a json
        """

        params = {
            'action': 'wbgetentities',
            'ids': entity_id,
            'format': 'json'
        }

        return mediawiki_api_call_helper(data=params, allow_anonymous=True, **kwargs)

    def clear(self, **kwargs) -> None:
        self._write(clear=True, **kwargs)

    def _write(self, data: Dict = None, summary: str = None, allow_anonymous: bool = False, clear: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Writes the item Json to the Wikibase instance and after successful write, updates the object with new ids and hashes generated by the Wikibase instance.
        For new items, also returns the new QIDs.

        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :return: the entity ID on successful write
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

        data = simplejson.JSONEncoder().encode(data)

        payload: Dict[str, Any] = {
            'action': 'wbeditentity',
            'data': data,
            'format': 'json',
            'summary': summary
        }

        if not summary:
            payload.pop('summary')

        if self.api.is_bot:
            payload.update({'bot': ''})

        if clear:
            payload.update({'clear': True})

        if self.id:
            payload.update({'id': self.id})
        else:
            payload.update({'new': self.type})

        if self.lastrevid:
            payload.update({'baserevid': self.lastrevid})

        if self.debug:
            print(payload)

        try:
            json_data = mediawiki_api_call_helper(data=payload, login=self.api.login, allow_anonymous=allow_anonymous, is_bot=self.api.is_bot, **kwargs)

            if 'error' in json_data and 'messages' in json_data['error']:
                error_msg_names = {x.get('name') for x in json_data['error']['messages']}
                if 'wikibase-validator-label-with-description-conflict' in error_msg_names:
                    raise NonUniqueLabelDescriptionPairError(json_data)

                raise MWApiError(json_data)

            if 'error' in json_data.keys():
                raise MWApiError(json_data)
        except Exception:
            print('Error while writing to the Wikibase instance')
            raise

        # after successful write, update this object with latest json, QID and parsed data types.
        self.id = json_data['entity']['id']
        if 'success' in json_data and 'entity' in json_data and 'lastrevid' in json_data['entity']:
            self.lastrevid = json_data['entity']['lastrevid']
        return json_data['entity']

    def init_fastrun(self, base_filter: Dict[str, str] = None, use_refs: bool = False, case_insensitive: bool = False) -> None:
        if base_filter is None:
            base_filter = {}

        if self.debug:
            print('Initialize Fast Run init_fastrun')
        # We search if we already have a FastRunContainer with the same parameters to re-use it
        for fast_run in BaseEntity.fast_run_store:
            if (fast_run.base_filter == base_filter) and (fast_run.use_refs == use_refs) and (fast_run.case_insensitive == case_insensitive) and (
                    fast_run.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
                self.fast_run_container = fast_run
                self.fast_run_container.current_qid = ''
                self.fast_run_container.base_data_type = BaseDataType
                if self.debug:
                    print("Found an already existing FastRunContainer")

        if not self.fast_run_container:
            if self.debug:
                print("Create a new FastRunContainer")
            self.fast_run_container = FastRunContainer(base_filter=base_filter, use_refs=use_refs, base_data_type=BaseDataType, case_insensitive=case_insensitive)
            BaseEntity.fast_run_store.append(self.fast_run_container)

    def fr_search(self, **kwargs) -> str:
        self.init_fastrun(**kwargs)

        if self.fast_run_container is None:
            raise ValueError("FastRunContainer is not initialized.")

        self.fast_run_container.load_item(self.claims)

        return self.fast_run_container.current_qid

    def write_required(self, base_filter: Dict[str, str] = None, **kwargs) -> bool:
        self.init_fastrun(base_filter=base_filter, **kwargs)

        if self.fast_run_container is None:
            raise ValueError("FastRunContainer is not initialized.")

        if base_filter is None:
            base_filter = {}

        claims_to_check = []
        for claim in self.claims:
            if claim.mainsnak.property_number in base_filter:
                claims_to_check.append(claim)

        return self.fast_run_container.write_required(data=claims_to_check, cqid=self.id)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
