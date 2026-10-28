from __future__ import annotations

import copy
import warnings
from abc import abstractmethod
from collections.abc import Callable
from typing import Any, Self

from wikibaseintegrator.models.basemodel import BaseModel
from wikibaseintegrator.models.qualifiers import Qualifiers
from wikibaseintegrator.models.reference import Reference
from wikibaseintegrator.models.references import References
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.models.snaks import Snaks
from wikibaseintegrator.wbi_enums import WikibaseRank, WikibaseSnakType


class Claim(BaseModel):
    """
    extend :func:`wikibaseintegrator.models.basemodel.BaseModel`

    :param qualifiers:
    :param id:
    :param rank:
    :param references: A References object, a list of Claim object or a list of list of Claim object
    """
    DTYPE = 'claim'

    def __init__(self, qualifiers: Qualifiers | None = None, id: str | None = None, rank: WikibaseRank | None = None, references: References | list[Claim | list[Claim]] | None = None,
                 snaktype: WikibaseSnakType = WikibaseSnakType.KNOWN_VALUE) -> None:
        """

        :param qualifiers:
        :param rank:
        :param references: A References object, a list of Claim object or a list of list of Claim object
        :param snaktype:
        """
        self.mainsnak = Snak(datatype=self.DTYPE, snaktype=snaktype)
        self.type = 'statement'
        self.qualifiers = qualifiers or Qualifiers()
        self.qualifiers_order = []
        self.id = id
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
                            raise ValueError("The references must be a References object or a list of Claim object")
                    ref.snaks = snaks
                elif isinstance(ref_list, Claim):
                    ref.snaks = Snaks().add(Snak().from_json(ref_list.get_json()['mainsnak']))
                elif isinstance(ref_list, Reference):
                    ref = ref_list
                self.references.add(reference=ref)
        elif references is not None:
            raise ValueError("The references must be a References object or a list of Claim object")

    @property
    def mainsnak(self) -> Snak:
        return self.__mainsnak

    @mainsnak.setter
    def mainsnak(self, value: Snak):
        self.__mainsnak = value

    @property
    def type(self) -> str | dict:
        return self.__type

    @type.setter
    def type(self, value: str | dict):
        self.__type = value

    @property
    def qualifiers(self) -> Qualifiers:
        return self.__qualifiers

    @qualifiers.setter
    def qualifiers(self, value: Qualifiers) -> None:
        assert isinstance(value, (Qualifiers, list))
        self.__qualifiers: Qualifiers = Qualifiers().set(value) if isinstance(value, list) else value

    @property
    def qualifiers_order(self) -> list[str]:
        return self.__qualifiers_order

    @qualifiers_order.setter
    def qualifiers_order(self, value: list[str]):
        self.__qualifiers_order = value

    @property
    def id(self) -> str | None:
        return self.__id

    @id.setter
    def id(self, value: str | None):
        self.__id = value

    @property
    def rank(self) -> WikibaseRank:
        return self.__rank

    @rank.setter
    def rank(self, value: WikibaseRank):
        """Parse the rank. The enum throws an error if it is not one of the recognized values"""
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

    def update(self, claim: Claim) -> None:
        self.mainsnak = claim.mainsnak
        self.qualifiers = claim.qualifiers
        self.qualifiers_order = claim.qualifiers_order
        self.rank = claim.rank
        self.references = claim.references

    def from_json(self, json_data: dict[str, Any]) -> Self:
        """

        :param json_data: a JSON representation of a Claim
        """
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

    def get_json(self) -> dict[str, Any]:
        json_data: dict[str, str | list[dict] | list[str] | dict[str, str] | dict[str, list] | None] = {
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
            if self.id:
                json_data['remove'] = ''
        return json_data

    def has_equal_qualifiers(self, other: Claim) -> bool:
        # check if the qualifiers are equal with the 'other' object
        self_qualifiers = copy.deepcopy(self.qualifiers)
        other_qualifiers = copy.deepcopy(other.qualifiers)

        if len(self_qualifiers) != len(other_qualifiers):
            return False

        for property_number in self_qualifiers.qualifiers:
            if property_number not in other_qualifiers.qualifiers:
                return False

            if len(self_qualifiers.qualifiers[property_number]) != len(other_qualifiers.qualifiers[property_number]):
                return False

            flg = [False for _ in range(len(self_qualifiers.qualifiers[property_number]))]
            for count, i in enumerate(self_qualifiers.qualifiers[property_number]):
                for q in other_qualifiers:
                    if i == q:
                        flg[count] = True
            if not all(flg):
                return False

        return True

    def reset_id(self):
        """
        Reset the ID of the current claim
        """
        self.id = None

    # TODO: rewrite this?
    def __contains__(self, item):
        if isinstance(item, Claim):
            return self == item

        if isinstance(item, str):
            return self.mainsnak.datavalue == item

        return False

    def __eq__(self, other):
        if isinstance(other, Claim):
            return self.mainsnak.datavalue == other.mainsnak.datavalue and self.mainsnak.property_number == other.mainsnak.property_number and self.has_equal_qualifiers(other)

        if isinstance(other, str):
            return self.mainsnak.property_number == other

        return NotImplemented

    def equals(self, that: Claim, include_ref: bool = False, fref: Callable | None = None) -> bool:
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
    def quals_equal(olditem: Claim, newitem: Claim) -> bool:
        """
        Tests for exactly identical qualifiers.
        """

        oldqual = olditem.qualifiers
        newqual = newitem.qualifiers

        return (len(oldqual) == len(newqual)) and all(x in oldqual for x in newqual)

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

    @staticmethod
    def ref_present(olditem: Claim, newitem: Claim) -> bool:
        """
        Tests if (1) there is a single ref in the new item and
        (2) if this single ref is present among the claims of the old item.
        """

        oldrefs = olditem.references
        newrefs = newitem.references

        if len(newrefs) != 1:
            warnings.warn("New item has more or less than 1 reference block.")
            return False

        def ref_equal(oldref: References, newref: References) -> bool:
            return (len(oldref) == len(newref)) and all(x in oldref for x in newref)

        return any(any(ref_equal(oldref, newref) for oldref in oldrefs) for newref in newrefs)

    @abstractmethod
    def get_sparql_value(self, **kwargs: Any) -> str | None:
        pass
