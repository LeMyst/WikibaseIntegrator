import copy
import datetime
import re

from wikibaseintegrator.wbi_config import config
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
            if isinstance(self.references, BaseDataType):
                self.references = [[self.references]]

            for ref_list in self.references:
                if isinstance(ref_list, BaseDataType):
                    ref_list = [ref_list]
                for reference in ref_list:
                    if not isinstance(reference, BaseDataType):
                        raise ValueError('A reference must be an instance of class BaseDataType.')

                    if reference.is_reference is False:
                        raise ValueError('A reference can\'t be declared as is_reference=False')
                    elif reference.is_reference is None:
                        reference.is_reference = True

        if not self.qualifiers:
            self.qualifiers = []
        else:
            if isinstance(self.qualifiers, BaseDataType):
                self.qualifiers = [self.qualifiers]

            for qualifier in self.qualifiers:
                if not isinstance(qualifier, BaseDataType):
                    raise ValueError('A qualifier must be an instance of class BaseDataType.')
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
                raise ValueError('Invalid prop_nr, format must be "P[0-9]+", got {}'.format(prop_nr))
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


class CommonsMedia(BaseDataType):
    """
    Implements the Wikibase data type for Wikimedia commons media files
    """
    DTYPE = 'commonsMedia'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The media file name from Wikimedia commons to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        self.value = None

        super(CommonsMedia, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(CommonsMedia, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class ExternalID(BaseDataType):
    """
    Implements the Wikibase data type 'external-id'
    """
    DTYPE = 'external-id'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The string to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(ExternalID, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(ExternalID, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class Form(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-form'
    """
    DTYPE = 'wikibase-form'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The form number to serve as a value using the format "L<Lexeme ID>-F<Form ID>" (example: L252248-F2)
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Form, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            pattern = re.compile(r'^L[0-9]+-F[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid form ID ({}), format must be 'L[0-9]+-F[0-9]+'".format(value))

            self.value = value

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'form',
                'id': self.value
            },
            'type': 'wikibase-entityid'
        }

        super(Form, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['id'], prop_nr=jsn['property'])


class GeoShape(BaseDataType):
    """
    Implements the Wikibase data type 'geo-shape'
    """
    DTYPE = 'geo-shape'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The GeoShape map file name in Wikimedia Commons to be linked
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(GeoShape, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Paris.map
            pattern = re.compile(r'^Data:((?![:|#]).)+\.map$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .map. In addition title should not contain characters like colon, hash or pipe.")
            self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(GeoShape, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class GlobeCoordinate(BaseDataType):
    """
    Implements the Wikibase data type for globe coordinates
    """
    DTYPE = 'globe-coordinate'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^geo:wktLiteral .
        }}
    '''

    def __init__(self, latitude, longitude, precision, prop_nr, globe=None, wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param latitude: Latitute in decimal format
        :type latitude: float or None
        :param longitude: Longitude in decimal format
        :type longitude: float or None
        :param precision: Precision of the position measurement
        :type precision: float or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        globe = config['COORDINATE_GLOBE_QID'] if globe is None else globe
        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        self.latitude = None
        self.longitude = None
        self.precision = None
        self.globe = None

        if globe.startswith('Q'):
            globe = wikibase_url + '/entity/' + globe

        value = (latitude, longitude, precision, globe)

        super(GlobeCoordinate, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        # TODO: Introduce validity checks for coordinates, etc.
        # TODO: Add check if latitude/longitude/precision is None
        self.latitude, self.longitude, self.precision, self.globe = value

        self.json_representation['datavalue'] = {
            'value': {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'precision': self.precision,
                'globe': self.globe
            },
            'type': 'globecoordinate'
        }

        self.value = (self.latitude, self.longitude, self.precision, self.globe)
        super(GlobeCoordinate, self).set_value(value=self.value)

    def get_sparql_value(self):
        return 'Point(' + str(self.latitude) + ', ' + str(self.longitude) + ')'

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(latitude=None, longitude=None, precision=None, prop_nr=jsn['property'],
                       snak_type=jsn['snaktype'])

        value = jsn['datavalue']['value']
        return cls(latitude=value['latitude'], longitude=value['longitude'], precision=value['precision'],
                   prop_nr=jsn['property'])


class ItemID(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-item' with a value being another item ID
    """
    DTYPE = 'wikibase-item'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/Q{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The item ID to serve as the value
        :type value: str with a 'Q' prefix, followed by several digits or only the digits without the 'Q' prefix
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(ItemID, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, (str, int)) or value is None, 'Expected str or int, found {} ({})'.format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^Q?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid item ID ({}), format must be 'Q[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'item',
                'numeric-id': self.value,
                'id': 'Q{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }

        super(ItemID, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['numeric-id'], prop_nr=jsn['property'])


class LocalMedia(BaseDataType):
    """
    Implements the data type for Wikibase local media files.
    The new data type is introduced via the LocalMedia extension
    https://github.com/ProfessionalWiki/WikibaseLocalMedia
    """
    DTYPE = 'localMedia'

    def __init__(self, value, prop_nr, is_reference=False, is_qualifier=False, snak_type='value', references=None,
                 qualifiers=None, rank='normal', check_qualifier_equality=True):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The media file name from the local Mediawiki to be used as the value
        :type value: str
        :param prop_nr: The property id for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(LocalMedia, self).__init__(value=value, snak_type=snak_type, data_type=self.DTYPE,
                                         is_reference=is_reference, is_qualifier=is_qualifier, references=references,
                                         qualifiers=qualifiers, rank=rank, prop_nr=prop_nr,
                                         check_qualifier_equality=check_qualifier_equality)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.json_representation['datavalue'] = {
            'value': value,
            'type': 'string'
        }

        super(LocalMedia, self).set_value(value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class Lexeme(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-lexeme'
    """
    DTYPE = 'wikibase-lexeme'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/L{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The lexeme number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Lexeme, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, (str, int)) or value is None, "Expected str or int, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^L?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid lexeme ID ({}), format must be 'L[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'lexeme',
                'numeric-id': self.value,
                'id': 'L{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }

        super(Lexeme, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['numeric-id'], prop_nr=jsn['property'])


class Math(BaseDataType):
    """
    Implements the Wikibase data type 'math' for mathematical formula in TEX format
    """
    DTYPE = 'math'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The string to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Math, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(Math, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class MonolingualText(BaseDataType):
    """
    Implements the Wikibase data type for Monolingual Text strings
    """
    DTYPE = 'monolingualtext'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> {value} .
        }}
    '''

    def __init__(self, text, prop_nr, language=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param text: The language specific string to be used as the value
        :type text: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param language: Specifies the language the value belongs to
        :type language: str
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        self.text = None
        self.language = config['DEFAULT_LANGUAGE'] if language is None else language

        value = (text, self.language)

        super(MonolingualText, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        self.text, self.language = value
        if self.text is not None:
            assert isinstance(self.text, str) or self.text is None, "Expected str, found {} ({})".format(type(self.text), self.text)
        elif self.snak_type == 'value':
            raise ValueError("Parameter 'text' can't be 'None' if 'snak_type' is 'value'")
        assert isinstance(self.language, str), "Expected str, found {} ({})".format(type(self.language), self.language)

        self.json_representation['datavalue'] = {
            'value': {
                'text': self.text,
                'language': self.language
            },
            'type': 'monolingualtext'
        }

        self.value = (self.text, self.language)
        super(MonolingualText, self).set_value(value=self.value)

    def get_sparql_value(self):
        return '"' + self.text.replace('"', r'\"') + '"@' + self.language

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(text=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])

        value = jsn['datavalue']['value']
        return cls(text=value['text'], prop_nr=jsn['property'], language=value['language'])


class MusicalNotation(BaseDataType):
    """
    Implements the Wikibase data type 'musical-notation'
    """
    DTYPE = 'musical-notation'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Values for that data type are strings describing music following LilyPond syntax.
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(MusicalNotation, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(MusicalNotation, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class Property(BaseDataType):
    """
    Implements the Wikibase data type 'property'
    """
    DTYPE = 'wikibase-property'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/P{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The property number to serve as a value
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Property, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, (str, int)) or value is None, "Expected str or int, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        elif isinstance(value, int):
            self.value = value
        else:
            pattern = re.compile(r'^P?([0-9]+)$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid property ID ({}), format must be 'P[0-9]+'".format(value))
            else:
                self.value = int(matches.group(1))

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'property',
                'numeric-id': self.value,
                'id': 'P{}'.format(self.value)
            },
            'type': 'wikibase-entityid'
        }

        super(Property, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['numeric-id'], prop_nr=jsn['property'])


class Quantity(BaseDataType):
    """
    Implements the Wikibase data type for quantities
    """
    DTYPE = 'quantity'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:decimal .
        }}
    '''

    def __init__(self, quantity, prop_nr, upper_bound=None, lower_bound=None, unit='1', wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param quantity: The quantity value
        :type quantity: float, str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param upper_bound: Upper bound of the value if it exists, e.g. for standard deviations
        :type upper_bound: float, str
        :param lower_bound: Lower bound of the value if it exists, e.g. for standard deviations
        :type lower_bound: float, str
        :param unit: The unit item URL or the QID a certain quantity has been measured in (https://www.wikidata.org/wiki/Wikidata:Units).
            The default is dimensionless, represented by a '1'
        :type unit: str
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        if unit.startswith('Q'):
            unit = wikibase_url + '/entity/' + unit

        self.quantity = None
        self.unit = None
        self.upper_bound = None
        self.lower_bound = None

        value = (quantity, unit, upper_bound, lower_bound)

        super(Quantity, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        self.quantity, self.unit, self.upper_bound, self.lower_bound = value

        if self.quantity is not None:
            self.quantity = self.format_amount(self.quantity)
            self.unit = str(self.unit)
            if self.upper_bound:
                self.upper_bound = self.format_amount(self.upper_bound)
            if self.lower_bound:
                self.lower_bound = self.format_amount(self.lower_bound)

            # Integrity checks for value and bounds
            try:
                for i in [self.quantity, self.upper_bound, self.lower_bound]:
                    if i:
                        float(i)
            except ValueError:
                raise ValueError("Value, bounds and units must parse as integers or float")

            if (self.lower_bound and self.upper_bound) and (float(self.lower_bound) > float(self.upper_bound)
                                                            or float(self.lower_bound) > float(self.quantity)):
                raise ValueError("Lower bound too large")

            if self.upper_bound and float(self.upper_bound) < float(self.quantity):
                raise ValueError("Upper bound too small")
        elif self.snak_type == 'value':
            raise ValueError("Parameter 'quantity' can't be 'None' if 'snak_type' is 'value'")

        self.json_representation['datavalue'] = {
            'value': {
                'amount': self.quantity,
                'unit': self.unit,
                'upperBound': self.upper_bound,
                'lowerBound': self.lower_bound
            },
            'type': 'quantity'
        }

        # remove bounds from json if they are undefined
        if not self.upper_bound:
            del self.json_representation['datavalue']['value']['upperBound']

        if not self.lower_bound:
            del self.json_representation['datavalue']['value']['lowerBound']

        self.value = (self.quantity, self.unit, self.upper_bound, self.lower_bound)
        super(Quantity, self).set_value(value=self.value)

    def get_sparql_value(self):
        return self.quantity

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(quantity=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])

        value = jsn['datavalue']['value']
        upper_bound = value['upperBound'] if 'upperBound' in value else None
        lower_bound = value['lowerBound'] if 'lowerBound' in value else None
        return cls(quantity=value['amount'], prop_nr=jsn['property'], upper_bound=upper_bound, lower_bound=lower_bound,
                   unit=value['unit'])

    @staticmethod
    def format_amount(amount):
        # Remove .0 by casting to int
        if float(amount) % 1 == 0:
            amount = int(float(amount))

        # Adding prefix + for positive number and 0
        if not str(amount).startswith('+') and float(amount) >= 0:
            amount = str('+{}'.format(amount))

        # return as string
        return str(amount)


class Sense(BaseDataType):
    """
    Implements the Wikibase data type 'wikibase-sense'
    """
    DTYPE = 'wikibase-sense'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{wb_url}/entity/{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Value using the format "L<Lexeme ID>-S<Sense ID>" (example: L252248-S123)
        :type value: str with a 'P' prefix, followed by several digits or only the digits without the 'P' prefix
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Sense, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            pattern = re.compile(r'^L[0-9]+-S[0-9]+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid sense ID ({}), format must be 'L[0-9]+-S[0-9]+'".format(value))

            self.value = value

        self.json_representation['datavalue'] = {
            'value': {
                'entity-type': 'sense',
                'id': self.value
            },
            'type': 'wikibase-entityid'
        }

        super(Sense, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value']['id'], prop_nr=jsn['property'])


class String(BaseDataType):
    """
    Implements the Wikibase data type 'string'
    """

    DTYPE = 'string'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The string to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(String, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(String, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class TabularData(BaseDataType):
    """
    Implements the Wikibase data type 'tabular-data'
    """
    DTYPE = 'tabular-data'

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: Reference to tabular data file on Wikimedia Commons.
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(TabularData, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            # TODO: Need to check if the value is a full URl like http://commons.wikimedia.org/data/main/Data:Taipei+Population.tab
            pattern = re.compile(r'^Data:((?![:|#]).)+\.tab$')
            matches = pattern.match(value)
            if not matches:
                raise ValueError("Value must start with Data: and end with .tab. In addition title should not contain characters like colon, hash or pipe.")
            self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(TabularData, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])


class Time(BaseDataType):
    """
    Implements the Wikibase data type with date and time values
    """
    DTYPE = 'time'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:dateTime .
        }}
    '''

    def __init__(self, time, prop_nr, before=0, after=0, precision=11, timezone=0, calendarmodel=None, wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param time: Explicit value for point in time, represented as a timestamp resembling ISO 8601
        :type time: str in the format '+%Y-%m-%dT%H:%M:%SZ', e.g. '+2001-12-31T12:01:13Z' or 'now'
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param before: explicit integer value for how many units after the given time it could be.
                       The unit is given by the precision.
        :type before: int
        :param after: explicit integer value for how many units before the given time it could be.
                      The unit is given by the precision.
        :type after: int
        :param precision: Precision value for dates and time as specified in the Wikibase data model
                          (https://www.wikidata.org/wiki/Special:ListDatatypes#time)
        :type precision: int
        :param timezone: The timezone which applies to the date and time as specified in the Wikibase data model
        :type timezone: int
        :param calendarmodel: The calendar model used for the date. URL to the Wikibase calendar model item or the QID.
        :type calendarmodel: str
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        calendarmodel = config['CALENDAR_MODEL_QID'] if calendarmodel is None else calendarmodel
        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url

        self.time = None
        self.before = None
        self.after = None
        self.precision = None
        self.timezone = None
        self.calendarmodel = None

        if calendarmodel.startswith('Q'):
            calendarmodel = wikibase_url + '/entity/' + calendarmodel

        value = (time, before, after, precision, timezone, calendarmodel)

        super(Time, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        self.time, self.before, self.after, self.precision, self.timezone, self.calendarmodel = value
        assert isinstance(self.time, str) or self.time is None, "Expected str, found {} ({})".format(type(self.time), self.time)

        if self.time is not None:
            if self.time == "now":
                self.time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            if not (self.time.startswith("+") or self.time.startswith("-")):
                self.time = "+" + self.time
            pattern = re.compile(r'^[+-][0-9]*-(?:1[0-2]|0[0-9])-(?:3[01]|0[0-9]|[12][0-9])T(?:2[0-3]|[01][0-9]):[0-5][0-9]:[0-5][0-9]Z$')
            matches = pattern.match(self.time)
            if not matches:
                raise ValueError("Time time must be a string in the following format: '+%Y-%m-%dT%H:%M:%SZ'")
            self.value = value
            if self.precision < 0 or self.precision > 15:
                raise ValueError("Invalid value for time precision, see https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON#time")
        elif self.snak_type == 'value':
            raise ValueError("Parameter 'time' can't be 'None' if 'snak_type' is 'value'")

        self.json_representation['datavalue'] = {
            'value': {
                'time': self.time,
                'before': self.before,
                'after': self.after,
                'precision': self.precision,
                'timezone': self.timezone,
                'calendarmodel': self.calendarmodel
            },
            'type': 'time'
        }

        self.value = (self.time, self.before, self.after, self.precision, self.timezone, self.calendarmodel)
        super(Time, self).set_value(value=self.value)

    def get_sparql_value(self):
        return self.time

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(time=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])

        value = jsn['datavalue']['value']
        return cls(time=value['time'], prop_nr=jsn['property'], before=value['before'], after=value['after'], precision=value['precision'], timezone=value['timezone'],
                   calendarmodel=value['calendarmodel'])


class Url(BaseDataType):
    """
    Implements the Wikibase data type for URL strings
    """
    DTYPE = 'url'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> <{value}> .
        }}
    '''

    def __init__(self, value, prop_nr, **kwargs):
        """
        Constructor, calls the superclass BaseDataType
        :param value: The URL to be used as the value
        :type value: str or None
        :param prop_nr: The item ID for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param is_reference: Whether this snak is a reference
        :type is_reference: boolean
        :param is_qualifier: Whether this snak is a qualifier
        :type is_qualifier: boolean
        :param snak_type: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snak_type: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super(Url, self).__init__(value=value, prop_nr=prop_nr, **kwargs)

        self.set_value(value)

    def set_value(self, value):
        assert isinstance(value, str) or value is None, "Expected str, found {} ({})".format(type(value), value)
        if value is None:
            self.value = value
        else:
            pattern = re.compile(r'^([a-z][a-z\d+.-]*):([^][<>\"\x00-\x20\x7F])+$')
            matches = pattern.match(value)

            if not matches:
                raise ValueError("Invalid URL {}".format(value))
            self.value = value

        self.json_representation['datavalue'] = {
            'value': self.value,
            'type': 'string'
        }

        super(Url, self).set_value(value=self.value)

    @classmethod
    @JsonParser
    def from_json(cls, jsn):
        if jsn['snaktype'] == 'novalue' or jsn['snaktype'] == 'somevalue':
            return cls(value=None, prop_nr=jsn['property'], snak_type=jsn['snaktype'])
        return cls(value=jsn['datavalue']['value'], prop_nr=jsn['property'])
