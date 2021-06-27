import re
from pprint import pprint

from wikibaseintegrator.models import Claim, Snak, Snaks, References, Reference
from wikibaseintegrator.wbi_jsonparser import JsonParser


class BaseDataType(Claim):
    """
    The base class for all Wikibase data types, they inherit from it
    """
    DTYPE = 'base-data-type'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}' .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, will be called by all data types.
        :param value: Data value of the Wikibase data snak
        :type value: str or int or tuple
        :param prop_nr: The property number a Wikibase snak belongs to
        :type prop_nr: A string with a prefixed 'P' and several digits e.g. 'P715' (Drugbank ID) or an int
        :param datatype: The Wikibase data type declaration of this snak
        :type datatype: str
        :param snaktype: The snak type of the Wikibase data snak, three values possible, depending if the value is a known (value), not existent (novalue) or
            unknown (somevalue). See Wikibase documentation.
        :type snaktype: a str of either 'value', 'novalue' or 'somevalue'
        :param references: A one level nested list with reference Wikibase snaks of base type BaseDataType,
            e.g. references=[[<BaseDataType>, <BaseDataType>], [<BaseDataType>]]
            This will create two references, the first one with two statements, the second with one
        :type references: A one level nested list with instances of BaseDataType or children of it.
        :param qualifiers: A list of qualifiers for the Wikibase mainsnak
        :type qualifiers: A list with instances of BaseDataType or children of it.
        :param is_reference: States if the snak is a reference, mutually exclusive with qualifier
        :type is_reference: boolean
        :param is_qualifier: States if the snak is a qualifier, mutually exlcusive with reference
        :type is_qualifier: boolean
        :param rank: The rank of a Wikibase mainsnak, should determine the status of a value
        :type rank: A string of one of three allowed values: 'normal', 'deprecated', 'preferred'
        :return:
        """

        super().__init__()
        self.value = value
        self.datatype = kwargs.pop('datatype', self.DTYPE)
        self.snaktype = kwargs.pop('snaktype', 'value')
        self.references = kwargs.pop('references', None)
        self.qualifiers = kwargs.pop('qualifiers', None)
        self.is_reference = kwargs.pop('is_reference', None)
        self.is_qualifier = kwargs.pop('is_qualifier', None)
        self.rank = kwargs.pop('rank', 'normal')

        self._statement_ref_mode = 'KEEP_GOOD'

        if not self.references:
            self.references = References()
        elif isinstance(self.references, Reference):
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
        else:
            for ref_list in self.references:
                for reference in ref_list:
                    if reference.is_reference is False:
                        raise ValueError('A reference can\'t be declared as is_reference=False')
                    elif reference.is_reference is None:
                        reference.is_reference = True

        if not self.qualifiers:
            self.qualifiers = Snaks()
        else:
            for qualifier in self.qualifiers:
                if qualifier.is_qualifier is False:
                    raise ValueError('A qualifier can\'t be declared as is_qualifier=False')
                elif qualifier.is_qualifier is None:
                    qualifier.is_qualifier = True

        if isinstance(prop_nr, int):
            self.property = 'P' + str(prop_nr)
        else:
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(prop_nr)

            if not matches:
                raise ValueError('Invalid prop_nr, format must be "P[0-9]+"')
            else:
                self.property = 'P' + str(matches.group(1))

        # Internal ID and hash are issued by the Wikibase instance
        self.id = None
        self.hash = None

        self.json_representation = {
            'snaktype': self.snaktype,
            'property': self.property,
            'datavalue': {},
            'datatype': self.datatype
        }

        if self.snaktype not in ['value', 'novalue', 'somevalue']:
            raise ValueError('{} is not a valid snak type'.format(self.snaktype))

        if self.value is None and self.snaktype == 'value':
            raise ValueError('Parameter \'value\' can\'t be \'None\' if \'snaktype\' is \'value\'')

        if self.is_qualifier and self.is_reference:
            raise ValueError('A claim cannot be a reference and a qualifer at the same time')
        if (len(self.references) > 0 or len(self.qualifiers) > 0) and (self.is_qualifier or self.is_reference):
            raise ValueError('Qualifiers or references cannot have references or qualifiers')

        self.mainsnak = Snak().from_json(self.json_representation)

    @property
    def statement_ref_mode(self):
        return self._statement_ref_mode

    @statement_ref_mode.setter
    def statement_ref_mode(self, value):
        """Set the reference mode for a statement, always overrides the global reference state."""
        valid_values = ['STRICT_KEEP', 'STRICT_KEEP_APPEND', 'STRICT_OVERWRITE', 'KEEP_GOOD', 'CUSTOM']
        if value not in valid_values:
            raise ValueError('Not an allowed reference mode, allowed values {}'.format(' '.join(valid_values)))

        self._statement_ref_mode = value

    def get_value(self):
        return self.value

    def get_sparql_value(self):
        return self.value

    def set_value(self, value):
        if value is None and self.snaktype not in {'novalue', 'somevalue'}:
            raise ValueError("If 'value' is None, snaktype must be novalue or somevalue")
        if self.snaktype in {'novalue', 'somevalue'}:
            del self.json_representation['datavalue']
        elif 'datavalue' not in self.json_representation:
            self.json_representation['datavalue'] = {}

        self.mainsnak = Snak().from_json(self.json_representation)

        self.value = value

    def get_references(self):
        return self.references

    def set_references(self, references):
        if len(references) > 0 and (self.is_qualifier or self.is_reference):
            raise ValueError("Qualifiers or references cannot have references")

        # Force clean duplicate references
        temp_references = []
        for reference in references:
            if reference not in temp_references:
                temp_references.append(reference)
        references = temp_references

        self.references = references

    def set_qualifiers(self, qualifiers):
        # TODO: introduce a check to prevent duplicate qualifiers, those are not allowed in Wikibase
        if len(qualifiers) > 0 and (self.is_qualifier or self.is_reference):
            raise ValueError("Qualifiers or references cannot have qualifiers")

        self.qualifiers = qualifiers

    def get_rank(self):
        if self.is_qualifier or self.is_reference:
            return ''
        else:
            return self.rank

    def set_rank(self, rank):
        if self.is_qualifier or self.is_reference:
            raise ValueError("References or qualifiers do not have ranks")

        valid_ranks = ['normal', 'deprecated', 'preferred']

        if rank not in valid_ranks:
            raise ValueError("{} not a valid rank".format(rank))

        self.rank = rank

    def get_id(self):
        return self.id

    def set_id(self, claim_id):
        self.id = claim_id

    def get_prop_nr(self):
        return self.property

    def set_prop_nr(self, prop_nr):
        if prop_nr[0] != 'P':
            raise ValueError("Invalid property number")

        self.property = prop_nr

    @classmethod
    @JsonParser
    def from_json(cls, json_representation):
        pass

    def equals(self, that, include_ref=False, fref=None):
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
        else:
            if self != that:
                return False
            if fref is None:
                return BaseDataType.refs_equal(self, that)
            else:
                return fref(self, that)

    @staticmethod
    def refs_equal(olditem, newitem):
        """
        tests for exactly identical references
        """

        oldrefs = olditem.references
        newrefs = newitem.references

        def ref_equal(oldref, newref):
            return True if (len(oldref) == len(newref)) and all(x in oldref for x in newref) else False

        if len(oldrefs) == len(newrefs) and all(any(ref_equal(oldref, newref) for oldref in oldrefs) for newref in newrefs):
            return True
        else:
            return False

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
