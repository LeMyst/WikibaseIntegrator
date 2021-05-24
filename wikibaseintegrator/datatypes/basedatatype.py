import copy
import re

from wikibaseintegrator.wbi_jsonparser import JsonParser


class BaseDataType(object):
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
        :param data_type: The Wikibase data type declaration of this snak
        :type data_type: str
        :param snak_type: The snak type of the Wikibase data snak, three values possible, depending if the value is a known (value), not existent (novalue) or
            unknown (somevalue). See Wikibase documentation.
        :type snak_type: a str of either 'value', 'novalue' or 'somevalue'
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
        :param check_qualifier_equality: When comparing two objects, test if qualifiers are equals between them. Default to true.
        :type check_qualifier_equality: boolean
        :param if_exists: Replace or append the statement. You can force an append if the statement already exists.
        :type if_exists: A string of one of three allowed values: 'REPLACE', 'APPEND', 'FORCE_APPEND', 'KEEP'
        :return:
        """

        self.value = value
        self.data_type = kwargs.pop('data_type', self.DTYPE)
        self.snak_type = kwargs.pop('snak_type', 'value')
        self.references = kwargs.pop('references', None)
        self.qualifiers = kwargs.pop('qualifiers', None)
        self.is_reference = kwargs.pop('is_reference', None)
        self.is_qualifier = kwargs.pop('is_qualifier', None)
        self.rank = kwargs.pop('rank', 'normal')
        self.check_qualifier_equality = kwargs.pop('check_qualifier_equality', True)
        self.if_exists = kwargs.pop('if_exists', 'REPLACE')

        self._statement_ref_mode = 'KEEP_GOOD'

        if not self.references:
            self.references = []
        else:
            for ref_list in self.references:
                for reference in ref_list:
                    if reference.is_reference is False:
                        raise ValueError('A reference can\'t be declared as is_reference=False')
                    elif reference.is_reference is None:
                        reference.is_reference = True

        if not self.qualifiers:
            self.qualifiers = []
        else:
            for qualifier in self.qualifiers:
                if qualifier.is_qualifier is False:
                    raise ValueError('A qualifier can\'t be declared as is_qualifier=False')
                elif qualifier.is_qualifier is None:
                    qualifier.is_qualifier = True

        if isinstance(prop_nr, int):
            self.prop_nr = 'P' + str(prop_nr)
        else:
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(prop_nr)

            if not matches:
                raise ValueError('Invalid prop_nr, format must be "P[0-9]+"')
            else:
                self.prop_nr = 'P' + str(matches.group(1))

        # Internal ID and hash are issued by the Wikibase instance
        self.id = ''
        self.hash = ''

        self.json_representation = {
            'snaktype': self.snak_type,
            'property': self.prop_nr,
            'datavalue': {},
            'datatype': self.data_type
        }

        if self.snak_type not in ['value', 'novalue', 'somevalue']:
            raise ValueError('{} is not a valid snak type'.format(self.snak_type))

        if self.if_exists not in ['REPLACE', 'APPEND', 'FORCE_APPEND', 'KEEP']:
            raise ValueError('{} is not a valid if_exists value'.format(self.if_exists))

        if self.value is None and self.snak_type == 'value':
            raise ValueError('Parameter \'value\' can\'t be \'None\' if \'snak_type\' is \'value\'')

        if self.is_qualifier and self.is_reference:
            raise ValueError('A claim cannot be a reference and a qualifer at the same time')
        if (len(self.references) > 0 or len(self.qualifiers) > 0) and (self.is_qualifier or self.is_reference):
            raise ValueError('Qualifiers or references cannot have references or qualifiers')

    def has_equal_qualifiers(self, other):
        # check if the qualifiers are equal with the 'other' object
        equal_qualifiers = True
        self_qualifiers = copy.deepcopy(self.get_qualifiers())
        other_qualifiers = copy.deepcopy(other.get_qualifiers())

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

    def __eq__(self, other):
        equal_qualifiers = self.has_equal_qualifiers(other)
        equal_values = self.get_value() == other.get_value() and self.get_prop_nr() == other.get_prop_nr()

        if not (self.check_qualifier_equality and other.check_qualifier_equality) and equal_values:
            return True
        elif equal_values and equal_qualifiers:
            return True
        else:
            return False

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
        if value is None and self.snak_type not in {'novalue', 'somevalue'}:
            raise ValueError("If 'value' is None, snak_type must be novalue or somevalue")
        if self.snak_type in {'novalue', 'somevalue'}:
            del self.json_representation['datavalue']
        elif 'datavalue' not in self.json_representation:
            self.json_representation['datavalue'] = {}

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

    def get_qualifiers(self):
        return self.qualifiers

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

    def set_hash(self, claim_hash):
        self.hash = claim_hash

    def get_hash(self):
        return self.hash

    def get_prop_nr(self):
        return self.prop_nr

    def set_prop_nr(self, prop_nr):
        if prop_nr[0] != 'P':
            raise ValueError("Invalid property number")

        self.prop_nr = prop_nr

    def get_json_representation(self):
        if self.is_qualifier or self.is_reference:
            tmp_json = {
                self.prop_nr: [self.json_representation]
            }
            if self.hash != '' and self.is_qualifier:
                self.json_representation.update({'hash': self.hash})

            return tmp_json
        else:
            ref_json = []
            for count, ref in enumerate(self.references):
                snaks_order = []
                snaks = {}
                ref_json.append({
                    'snaks': snaks,
                    'snaks-order': snaks_order
                })
                for sub_ref in ref:
                    prop_nr = sub_ref.get_prop_nr()
                    # set the hash for the reference block
                    if sub_ref.get_hash() != '':
                        ref_json[count].update({'hash': sub_ref.get_hash()})
                    tmp_json = sub_ref.get_json_representation()

                    # if more reference values with the same property number, append to its specific property list.
                    if prop_nr in snaks:
                        snaks[prop_nr].append(tmp_json[prop_nr][0])
                    else:
                        snaks.update(tmp_json)
                    snaks_order.append(prop_nr)

            qual_json = {}
            qualifiers_order = []
            for qual in self.qualifiers:
                prop_nr = qual.get_prop_nr()
                if prop_nr in qual_json:
                    qual_json[prop_nr].append(qual.get_json_representation()[prop_nr][0])
                else:
                    qual_json.update(qual.get_json_representation())
                qualifiers_order.append(qual.get_prop_nr())

            if hasattr(self, 'remove'):
                statement = {
                    'remove': ''
                }
            else:
                statement = {
                    'mainsnak': self.json_representation,
                    'type': 'statement',
                    'rank': self.rank
                }
                if qual_json:
                    statement['qualifiers'] = qual_json
                if qualifiers_order:
                    statement['qualifiers-order'] = qualifiers_order
                if ref_json:
                    statement['references'] = ref_json
            if self.id != '':
                statement.update({'id': self.id})

            return statement

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
