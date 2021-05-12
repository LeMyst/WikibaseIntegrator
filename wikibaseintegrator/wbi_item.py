import copy

from wikibaseintegrator import wbi_functions
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_core import Core
from wikibaseintegrator.wbi_datatype import BaseDataType
from wikibaseintegrator.wbi_exceptions import (IDMissingError, SearchOnlyError)
from wikibaseintegrator.wbi_fastrun import FastRunContainer


class Item(Core):
    fast_run_store = []
    distinct_value_props = {}

    def __init__(self, item_id='', new_item=False, data=None, mediawiki_api_url=None, sparql_endpoint_url=None, wikibase_url=None, fast_run=False, fast_run_base_filter=None,
                 fast_run_use_refs=False, ref_handler=None, global_ref_mode='KEEP_GOOD', good_refs=None, keep_good_ref_statements=False, search_only=False, item_data=None,
                 user_agent=None, core_props=None, core_prop_match_thresh=0.66, property_constraint_pid=None, distinct_values_constraint_qid=None, fast_run_case_insensitive=False,
                 debug=False) -> None:
        """
        constructor
        :param item_id: Wikibase item id
        :type item_id: str
        :param new_item: This parameter lets the user indicate if a new item should be created
        :type new_item: bool
        :param data: a dictionary with property strings as keys and the data which should be written to a item as the property values
        :type data: list[BaseDataType] or BaseDataType or None
        :param mediawiki_api_url:
        :type mediawiki_api_url: str
        :param sparql_endpoint_url:
        :type sparql_endpoint_url: str
        :param wikibase_url:
        :type wikibase_url: str
        :param fast_run: True if this item should be run in fastrun mode, otherwise False. User setting this to True should also specify the
            fast_run_base_filter for these item types
        :type fast_run: bool
        :param fast_run_base_filter: A property value dict determining the Wikibase property and the corresponding value which should be used as a filter for
            this item type. Several filter criteria can be specified. The values can be either Wikibase item QIDs, strings or empty strings if the value should
            be a variable in SPARQL.
            Example: {'P352': '', 'P703': 'Q15978631'} if the basic common type of things this bot runs on is human proteins (specified by Uniprot IDs (P352)
            and 'found in taxon' homo sapiens 'Q15978631').
        :type fast_run_base_filter: dict
        :param fast_run_use_refs: If `True`, fastrun mode will consider references in determining if a statement should be updated and written to Wikibase.
            Otherwise, only the value and qualifiers are used. Default: False
        :type fast_run_use_refs: bool
        :param ref_handler: This parameter defines a function that will manage the reference handling in a custom manner. This argument should be a function
            handle that accepts two arguments, the old/current statement (first argument) and new/proposed/to be written statement (second argument), both of
            type: a subclass of BaseDataType. The function should return an new item that is the item to be written. The item's values properties or qualifiers
            should not be modified; only references. This function is also used in fastrun mode. This will only be used if the ref_mode is set to "CUSTOM".
        :type ref_handler: function
        :param global_ref_mode: sets the reference handling mode for an item. Four modes are possible, 'STRICT_KEEP' keeps all references as they are,
        'STRICT_KEEP_APPEND' keeps the references as they are and appends new ones. 'STRICT_OVERWRITE' overwrites all existing references for given.
        'KEEP_GOOD' will use the refs defined in good_refs. 'CUSTOM' will use the function defined in ref_handler
        :type global_ref_mode: str
        :param good_refs: This parameter lets the user define blocks of good references. It is a list of dictionaries. One block is a dictionary with Wikidata
            properties as keys and potential values as the required value for a property. There can be arbitrarily many key: value pairs in one reference block.
            Example: [{'P248': 'Q905695', 'P352': None, 'P407': None, 'P1476': None, 'P813': None}] This example contains one good reference block, stated in:
            Uniprot, Uniprot ID, title of Uniprot entry, language of work and date when the information has been retrieved. A None type indicates that the value
            varies from reference to reference. In this case, only the value for the Wikidata item for the Uniprot database stays stable over all of these
            references. Key value pairs work here, as Wikidata references can hold only one value for one property. The number of good reference blocks is not
            limited. This parameter OVERRIDES any other reference mode set!!
        :type good_refs: list[dict]
        :param keep_good_ref_statements: Do not delete any statement which has a good reference, either defined in the good_refs list or by any other
            referencing mode.
        :type keep_good_ref_statements: bool
        :param search_only: If this flag is set to True, the data provided will only be used to search for the corresponding Wikibase item, but no actual data
            updates will performed. This is useful, if certain states or values on the target item need to be checked before certain data is written to it. In
            order to write new data to the item, the method update() will take data, modify the Wikibase item and a write() call will then perform the actual
            write to the Wikibase instance.
        :type search_only: bool
        :param item_data: A Python JSON object corresponding to the item in item_id. This can be used in conjunction with item_id in order to provide raw data.
        :type item_data:
        :param user_agent: The user agent string to use when making http requests
        :type user_agent: str
        :param core_props: Core properties are used to retrieve an item based on `data` if a `item_id` is not given. This is a set of PIDs to use. If None,
            all Wikibase properties with a distinct values constraint will be used. (see: get_core_props)
        :type core_props: set
        :param core_prop_match_thresh: The proportion of core props that must match during retrieval of an item when the item_id is not specified.
        :type core_prop_match_thresh: float
        :param property_constraint_pid:
        :param distinct_values_constraint_qid:
        :param fast_run_case_insensitive:
        :param debug: Enable debug output.
        :type debug: boolean
        """

        super().__init__()
        self.core_prop_match_thresh = core_prop_match_thresh
        self.item_id = item_id
        self.new_item = new_item
        self.mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
        self.sparql_endpoint_url = config['SPARQL_ENDPOINT_URL'] if sparql_endpoint_url is None else sparql_endpoint_url
        self.wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url
        self.property_constraint_pid = config['PROPERTY_CONSTRAINT_PID'] if property_constraint_pid is None else property_constraint_pid
        self.distinct_values_constraint_qid = config['DISTINCT_VALUES_CONSTRAINT_QID'] if distinct_values_constraint_qid is None else distinct_values_constraint_qid
        if data is None:
            self.data = []
        elif isinstance(data, list) and all(isinstance(x, BaseDataType) for x in data):
            self.data = data
        elif isinstance(data, BaseDataType):
            self.data = [data]
        else:
            raise TypeError("`data` must be a list of BaseDataType or an instance of BaseDataType")
        self.fast_run = fast_run
        self.fast_run_base_filter = fast_run_base_filter
        self.fast_run_use_refs = fast_run_use_refs
        self.fast_run_case_insensitive = fast_run_case_insensitive
        self.ref_handler = ref_handler
        self.global_ref_mode = global_ref_mode
        self.good_refs = good_refs
        self.keep_good_ref_statements = keep_good_ref_statements
        self.search_only = search_only
        self.item_data = item_data
        self.user_agent = config['USER_AGENT_DEFAULT'] if user_agent is None else user_agent

        self.statements = []
        self.original_statements = []
        self.entity_metadata = {}
        self.fast_run_container = None
        if self.search_only:
            self.require_write = False
        else:
            self.require_write = True
        self.sitelinks = {}
        self.lastrevid = None  # stores last revisionid after a write occurs

        if fast_run_case_insensitive and not self.search_only:
            raise ValueError("If using fast run case insensitive, search_only must be set")

        if self.ref_handler and not callable(self.ref_handler):
            raise TypeError("ref_handler must be callable")
        if self.global_ref_mode == 'CUSTOM' and self.ref_handler is None:
            raise ValueError("If using a custom ref mode, ref_handler must be set")

        if (core_props is None) and (self.sparql_endpoint_url not in Item.distinct_value_props):
            Item.distinct_value_props[self.sparql_endpoint_url] = wbi_functions.get_distinct_value_props(self.sparql_endpoint_url,
                                                                                                         self.wikibase_url,
                                                                                                         self.property_constraint_pid,
                                                                                                         self.distinct_values_constraint_qid)
        self.core_props = core_props if core_props is not None else Item.distinct_value_props[self.sparql_endpoint_url]

        if self.fast_run:
            self.init_fastrun()
            if self.debug:
                if self.require_write:
                    if self.search_only:
                        print("Successful fastrun, search_only mode, we can't determine if data is up to date.")
                    else:
                        print("Successful fastrun, because no full data match you need to update the item.")
                else:
                    print("Successful fastrun, no write to Wikibase instance required.")

        if self.item_id != '' and self.create_new_item:
            raise IDMissingError("Cannot create a new item, when an identifier is given.")
        elif self.new_item and len(self.data) > 0:
            self.create_new_item = True
            self.__construct_claim_json()
        elif self.require_write or self.search_only:
            self.init_data_load()

    def init_fastrun(self):
        # We search if we already have a FastRunContainer with the same parameters to re-use it
        for c in Item.fast_run_store:
            if (c.base_filter == self.fast_run_base_filter) and (c.use_refs == self.fast_run_use_refs) and (c.sparql_endpoint_url == self.sparql_endpoint_url):
                self.fast_run_container = c
                self.fast_run_container.ref_handler = self.ref_handler
                self.fast_run_container.current_qid = ''
                self.fast_run_container.base_data_type = BaseDataType
                self.fast_run_container.engine = self.__class__
                self.fast_run_container.mediawiki_api_url = self.mediawiki_api_url
                self.fast_run_container.wikibase_url = self.wikibase_url
                self.fast_run_container.debug = self.debug
                if self.debug:
                    print("Found an already existing FastRunContainer")

        if not self.fast_run_container:
            self.fast_run_container = FastRunContainer(base_filter=self.fast_run_base_filter,
                                                       base_data_type=BaseDataType,
                                                       engine=self.__class__,
                                                       sparql_endpoint_url=self.sparql_endpoint_url,
                                                       mediawiki_api_url=self.mediawiki_api_url,
                                                       wikibase_url=self.wikibase_url,
                                                       use_refs=self.fast_run_use_refs,
                                                       ref_handler=self.ref_handler,
                                                       case_insensitive=self.fast_run_case_insensitive,
                                                       debug=self.debug)
            Item.fast_run_store.append(self.fast_run_container)

        if not self.search_only:
            self.require_write = self.fast_run_container.write_required(self.data, cqid=self.item_id)
            # set item id based on fast run data
            if not self.require_write and not self.item_id:
                self.item_id = self.fast_run_container.current_qid
        else:
            self.fast_run_container.load_item(self.data)
            # set item id based on fast run data
            if not self.item_id:
                self.item_id = self.fast_run_container.current_qid

    def update(self, data):
        """
        This method takes data, and modifies the Wikidata item. This works together with the data already provided via the constructor or if the constructor is
        being instantiated with search_only=True. In the latter case, this allows for checking the item data before deciding which new data should be written to
        the Wikidata item. The actual write to Wikidata only happens on calling of the write() method. If data has been provided already via the constructor,
        data provided via the update() method will be appended to these data.
        :param data: A list of Wikidata statment items inheriting from BaseDataType
        :type data: list
        """

        if self.search_only:
            raise SearchOnlyError

        assert type(data) == list

        self.data.extend(data)
        self.statements = copy.deepcopy(self.original_statements)

        if self.debug:
            print(self.data)

        if self.fast_run:
            self.init_fastrun()

        if self.require_write and self.fast_run:
            self.init_data_load()
            self.__construct_claim_json()
            self.__check_integrity()
        elif not self.fast_run:
            self.__construct_claim_json()
            self.__check_integrity()

    def get_property_list(self):
        """
        List of properties on the current item
        :return: a list of property ID strings (Pxxxx).
        """

        property_list = set()
        for x in self.statements:
            property_list.add(x.get_prop_nr())

        return list(property_list)

    def get_sitelink(self, site):
        """
        A method to access the interwiki links in the json.model
        :param site: The Wikipedia site the interwiki/sitelink should be returned for
        :return: The interwiki/sitelink string for the specified Wikipedia will be returned.
        """

        if site in self.sitelinks:
            return self.sitelinks[site]
        else:
            return None

    def set_sitelink(self, site, title, badges=()):
        """
        Set sitelinks to corresponding Wikipedia pages
        :param site: The Wikipedia page a sitelink is directed to (e.g. 'enwiki')
        :param title: The title of the Wikipedia page the sitelink is directed to
        :param badges: An iterable containing Wikipedia badge strings.
        :return:
        """

        if self.search_only:
            raise SearchOnlyError

        sitelink = {
            'site': site,
            'title': title,
            'badges': badges
        }
        self.json_representation['sitelinks'][site] = sitelink
        self.sitelinks[site] = sitelink

    def count_references(self, prop_id):
        counts = {}
        for claim in self.get_json_representation()['claims'][prop_id]:
            counts[claim['id']] = len(claim['references'])
        return counts

    def get_reference_properties(self, prop_id):
        references = []
        statements = [x for x in self.get_json_representation()['claims'][prop_id] if 'references' in x]
        for statement in statements:
            for reference in statement['references']:
                references.append(reference['snaks'].keys())
        return references

    def get_qualifier_properties(self, prop_id):
        qualifiers = []
        for statements in self.get_json_representation()['claims'][prop_id]:
            qualifiers.append(statements['qualifiers'].keys())
        return qualifiers
