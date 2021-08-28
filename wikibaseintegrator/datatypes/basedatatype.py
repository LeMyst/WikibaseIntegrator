from wikibaseintegrator.models import Claim, Snak, Snaks, References, Reference


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

    def __init__(self, prop_nr=None, **kwargs):
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
        :param rank: The rank of a Wikibase mainsnak, should determine the status of a value
        :type rank: A string of one of three allowed values: 'normal', 'deprecated', 'preferred'
        :return:
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

        self.value = None
        self.mainsnak.property_number = prop_nr or None

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        if not value:
            self.mainsnak.snaktype = 'novalue'
        self.__value = value

    def get_sparql_value(self):
        return self.mainsnak.datavalue['value']

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
