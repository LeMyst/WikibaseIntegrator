from __future__ import annotations

from typing import Any, Callable, List, Type, Union

from wikibaseintegrator.models import Claim, Reference, References, Snak, Snaks


class BaseDataType(Claim):
    """
    The base class for all Wikibase data types, they inherit from it
    """
    DTYPE = 'base-data-type'
    subclasses: List[Type[BaseDataType]] = []
    sparql_query: str = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}' .
        }}
    '''
    references: References

    def __init__(self, prop_nr: Union[int, str] = None, **kwargs: Any):
        """
        Constructor, will be called by all data types.

        :param prop_nr: The property number a Wikibase snak belongs to
        """

        super().__init__(**kwargs)

        if isinstance(self.references, Reference):
            self.references = References().add(self.references)
        elif isinstance(self.references, list):
            references = References()
            for ref_list in self.references:
                reference = Reference()
                if isinstance(ref_list, list):
                    snaks = Snaks()
                    for ref_claim in ref_list:
                        if isinstance(ref_claim, Claim):
                            snaks.add(Snak().from_json(ref_claim.get_json()['mainsnak']))
                            references.add(reference=reference)
                        else:
                            raise ValueError
                    reference.snaks = snaks
                elif isinstance(ref_list, Claim):
                    reference.snaks = Snaks().add(Snak().from_json(ref_list.get_json()['mainsnak']))
                elif isinstance(ref_list, Reference):
                    reference = ref_list
                references.add(reference=reference)
            self.references = references

        self.mainsnak.property_number = prop_nr or None
        # self.subclasses.append(self)

    # Allow registration of subclasses of BaseDataType into BaseDataType.subclasses
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)

    def _get_sparql_value(self) -> str:
        return self.mainsnak.datavalue['value']

    def equals(self, that: BaseDataType, include_ref: bool = False, fref: Callable = None) -> bool:
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
            return BaseDataType.refs_equal(self, that)

        return fref(self, that)

    @staticmethod
    def refs_equal(olditem: BaseDataType, newitem: BaseDataType) -> bool:
        """
        tests for exactly identical references
        """

        oldrefs = olditem.references
        newrefs = newitem.references

        def ref_equal(oldref: References, newref: References) -> bool:
            return (len(oldref) == len(newref)) and all(x in oldref for x in newref)

        return len(oldrefs) == len(newrefs) and all(any(ref_equal(oldref, newref) for oldref in oldrefs) for newref in newrefs)
