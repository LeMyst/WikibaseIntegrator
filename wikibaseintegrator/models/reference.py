from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Union

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists

if TYPE_CHECKING:
    from wikibaseintegrator.models.claim import Claim


class Reference(BaseModel):
    def __init__(self, snaks: Snaks = None, snaks_order: List = None):
        self.hash = None
        self.snaks = snaks or Snaks()
        self.snaks_order = snaks_order or []

    @property
    def hash(self):
        return self.__hash

    @hash.setter
    def hash(self, value):
        self.__hash = value

    @property
    def snaks(self):
        return self.__snaks

    @snaks.setter
    def snaks(self, value):
        self.__snaks = value

    @property
    def snaks_order(self):
        return self.__snaks_order

    @snaks_order.setter
    def snaks_order(self, value):
        self.__snaks_order = value

    # TODO: implement action_if_exists
    def add(self, snak: Union[Snak, Claim] = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL) -> Reference:
        from wikibaseintegrator.models.claims import Claim
        if isinstance(snak, Claim):
            snak = Snak().from_json(snak.get_json()['mainsnak'])

        if snak is not None:
            assert isinstance(snak, Snak)

        self.snaks.add(snak)

        return self

    def from_json(self, json_data: Dict[str, Any]) -> Reference:
        self.hash = json_data['hash']
        self.snaks = Snaks().from_json(json_data['snaks'])
        self.snaks_order = json_data['snaks-order']

        return self

    def get_json(self) -> Dict[str, Union[Dict, List]]:
        json_data: Dict[str, Union[Dict, List]] = {
            'snaks': self.snaks.get_json(),
            'snaks-order': self.snaks_order
        }
        return json_data

    def __iter__(self):
        return iter(self.snaks)

    def __len__(self):
        return len(self.snaks)
