from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Union

from wikibaseintegrator.models.qualifiers import Qualifiers
from wikibaseintegrator.models.references import Reference, References
from wikibaseintegrator.models.snaks import Snak, Snaks
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseRank


class Claims:
    def __init__(self):
        self.claims = {}

    @property
    def claims(self):
        return self.__claims

    @claims.setter
    def claims(self, claims):
        self.__claims = claims

    def get(self, property: str = None) -> List:
        return self.claims[property]

    def add(self, claims: Union[list, Claim, None] = None, action_if_exists: ActionIfExists = ActionIfExists.REPLACE) -> Claims:
        """

        :param claims:
        :param action_if_exists: Replace or append the statement. You can force an append if the statement already exists.
        :type action_if_exists: One of the values of the enum ActionIfExists: REPLACE, APPEND, FORCE_APPEND, KEEP
        :return: Claims
        """

        if action_if_exists not in ActionIfExists:
            raise ValueError(f'{action_if_exists} is not a valid action_if_exists value. Use the enum ActionIfExists')

        if isinstance(claims, Claim):
            claims = [claims]
        elif not isinstance(claims, list):
            raise ValueError

        # TODO: Don't replace if claim is the same
        if action_if_exists == ActionIfExists.REPLACE:
            for claim in claims:
                if claim is not None:
                    assert isinstance(claim, Claim)
                property = claim.mainsnak.property_number
                if property in self.claims:
                    for claim_to_remove in self.claims[property]:
                        if claim_to_remove not in claims:
                            claim_to_remove.remove()

        for claim in claims:
            if claim is not None:
                assert isinstance(claim, Claim)
            property = claim.mainsnak.property_number

            if property not in self.claims:
                self.claims[property] = []

            if action_if_exists == ActionIfExists.KEEP:
                if len(self.claims[property]) == 0:
                    self.claims[property].append(claim)
            elif action_if_exists == ActionIfExists.FORCE_APPEND:
                self.claims[property].append(claim)
            elif action_if_exists == ActionIfExists.APPEND:
                if claim not in self.claims[property]:
                    self.claims[property].append(claim)
            elif action_if_exists == ActionIfExists.REPLACE:
                if claim not in self.claims[property]:
                    self.claims[property].append(claim)

        return self

    def from_json(self, json_data: Dict[str, Any]) -> Claims:
        for property in json_data:
            for claim in json_data[property]:
                from wikibaseintegrator.datatypes import BaseDataType
                if 'datatype' in claim['mainsnak']:
                    data_type = [x for x in BaseDataType.subclasses if x.DTYPE == claim['mainsnak']['datatype']][0]
                else:
                    data_type = BaseDataType
                self.add(claims=data_type().from_json(claim), action_if_exists=ActionIfExists.FORCE_APPEND)

        return self

    def get_json(self) -> Dict[str, list]:
        json_data: Dict[str, list] = {}
        for property in self.claims:
            if property not in json_data:
                json_data[property] = []
            for claim in self.claims[property]:
                json_data[property].append(claim.get_json())
        return json_data

    def clear(self) -> None:
        self.claims = {}

    def __len__(self):
        return len(self.claims)

    def __iter__(self):
        iterate = []
        for claim in self.claims.values():
            iterate.extend(claim)
        return iter(iterate)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class Claim:
    DTYPE = 'claim'

    def __init__(self, qualifiers: Qualifiers = None, rank: WikibaseRank = None, references: Union[References, List[Union[Claim, List[Claim]]]] = None) -> None:
        self.mainsnak = Snak(datatype=self.DTYPE)
        self.type = 'statement'
        self.qualifiers = qualifiers or Qualifiers()
        self.qualifiers_order = []
        self.id = None
        self.rank = rank or WikibaseRank.NORMAL
        self.removed = False

        self.references = References()

        if isinstance(references, References):
            self.references = references
        elif isinstance(references, list):
            for ref_list in references:
                ref = Reference()
                if isinstance(ref_list, list):
                    snaks = Snaks()
                    for ref_claim in ref_list:
                        if isinstance(ref_claim, Claim):
                            snaks.add(Snak().from_json(ref_claim.get_json()['mainsnak']))
                        else:
                            raise ValueError
                    ref.snaks = snaks
                elif isinstance(ref_list, Claim):
                    ref.snaks = Snaks().add(Snak().from_json(ref_list.get_json()['mainsnak']))
                elif isinstance(ref_list, Reference):
                    ref = ref_list
                self.references.add(reference=ref)

    @property
    def mainsnak(self) -> Snak:
        return self.__mainsnak

    @mainsnak.setter
    def mainsnak(self, value: Snak):
        self.__mainsnak = value

    @property
    def type(self) -> Union[str, Dict]:
        return self.__type

    @type.setter
    def type(self, value: Union[str, Dict]):
        self.__type = value

    @property
    def qualifiers(self) -> Qualifiers:
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value: Qualifiers) -> None:
        assert isinstance(value, (Qualifiers, list))
        if isinstance(value, list):
            self.__qualifiers = Qualifiers().set(value)
        else:
            self.__qualifiers = value

    @property
    def qualifiers_order(self) -> List[str]:
        return self.__qualifiers_order

    @qualifiers_order.setter
    def qualifiers_order(self, value: List[str]):
        self.__qualifiers_order = value

    @property
    def id(self) -> Optional[str]:
        return self.__id

    @id.setter
    def id(self, value: Optional[str]):
        self.__id = value

    @property
    def rank(self) -> WikibaseRank:
        return self.__rank

    @rank.setter
    def rank(self, value: WikibaseRank):
        """Parse the rank. The enum thows an error if it is not one of the recognized values"""
        self.__rank = WikibaseRank(value)

    @property
    def references(self) -> References:
        return self.__references

    @references.setter
    def references(self, value: References):
        self.__references = value

    @property
    def removed(self) -> bool:
        return self.__removed

    @removed.setter
    def removed(self, value: bool):
        self.__removed = value

    def remove(self, remove=True) -> None:
        self.removed = remove

    def from_json(self, json_data: Dict[str, Any]) -> Claim:
        self.mainsnak = Snak().from_json(json_data['mainsnak'])
        self.type = str(json_data['type'])
        if 'qualifiers' in json_data:
            self.qualifiers = Qualifiers().from_json(json_data['qualifiers'])
        if 'qualifiers-order' in json_data:
            self.qualifiers_order = list(json_data['qualifiers-order'])
        self.id = str(json_data['id'])
        self.rank: WikibaseRank = WikibaseRank(json_data['rank'])
        if 'references' in json_data:
            self.references = References().from_json(json_data['references'])

        return self

    def get_json(self) -> Dict[str, Any]:
        json_data: Dict[str, Union[str, list, dict, None]] = {
            'mainsnak': self.mainsnak.get_json(),
            'type': self.type,
            'id': self.id,
            'rank': self.rank.value
        }
        # Remove id if it's a temporary one
        if not self.id:
            del json_data['id']
        if len(self.qualifiers) > 0:
            json_data['qualifiers'] = self.qualifiers.get_json()
            json_data['qualifiers-order'] = list(self.qualifiers_order)
        if len(self.references) > 0:
            json_data['references'] = self.references.get_json()
        if self.removed:
            json_data['remove'] = ''
        return json_data

    def has_equal_qualifiers(self, other: Claim) -> bool:
        # check if the qualifiers are equal with the 'other' object
        equal_qualifiers = True
        self_qualifiers = copy.deepcopy(self.qualifiers)
        other_qualifiers = copy.deepcopy(other.qualifiers)

        if len(self_qualifiers) != len(other_qualifiers):
            equal_qualifiers = False
        else:
            flg = [False for _ in range(len(self_qualifiers))]
            for count, i in enumerate(self_qualifiers):
                for q in other_qualifiers:
                    if i == q:
                        flg[count] = True
            if not all(flg):
                equal_qualifiers = False

        return equal_qualifiers

    def __contains__(self, item):
        if isinstance(item, Claim):
            return self == item

        if isinstance(item, str):
            return self.mainsnak.datavalue == item

        raise TypeError

    def __eq__(self, other):
        if isinstance(other, Claim):
            return self.mainsnak.datavalue == other.mainsnak.datavalue and self.mainsnak.property_number == other.mainsnak.property_number and self.has_equal_qualifiers(other)
        raise TypeError

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )

    def equals(self, that: Claim, include_ref: bool = False, fref: Callable = None) -> bool:
        """
        Tests for equality of two statements.
        If comparing references, the order of the arguments matters!!!
        self is the current statement, the next argument is the new statement.
        Allows passing in a function to use to compare the references 'fref'. Default is equality.
        fref accepts two arguments 'oldrefs' and 'newrefs', each of which are a list of references,
        where each reference is a list of statements
        """

        if not include_ref:
            # return the result of BaseDataType.__eq__, which is testing for equality of value and qualifiers
            return self == that

        if self != that:
            return False

        if fref is None:
            return Claim.refs_equal(self, that)

        return fref(self, that)

    @staticmethod
    def refs_equal(olditem: Claim, newitem: Claim) -> bool:
        """
        tests for exactly identical references
        """

        oldrefs = olditem.references
        newrefs = newitem.references

        def ref_equal(oldref: References, newref: References) -> bool:
            return (len(oldref) == len(newref)) and all(x in oldref for x in newref)

        return len(oldrefs) == len(newrefs) and all(any(ref_equal(oldref, newref) for oldref in oldrefs) for newref in newrefs)
