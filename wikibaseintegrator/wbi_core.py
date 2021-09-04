import copy
import json
from collections import defaultdict

from wikibaseintegrator import wbi_functions
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_datatype import BaseDataType
from wikibaseintegrator.wbi_exceptions import (IDMissingError, SearchError, SearchOnlyError, NonUniqueLabelDescriptionPairError, MWApiError, CorePropIntegrityException,
                                               ManualInterventionReqException)
from wikibaseintegrator.wbi_fastrun import FastRunContainer


class ItemEngine(object):
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

    fast_run_store = []
    distinct_value_props = {}

    def __init__(self, item_id='', new_item=False, data=None, mediawiki_api_url=None, sparql_endpoint_url=None, wikibase_url=None, fast_run=False, fast_run_base_filter=None,
                 fast_run_use_refs=False, ref_handler=None, global_ref_mode='KEEP_GOOD', good_refs=None, keep_good_ref_statements=False, search_only=False, item_data=None,
                 user_agent=None, core_props=None, core_prop_match_thresh=0.66, property_constraint_pid=None, distinct_values_constraint_qid=None, fast_run_case_insensitive=False,
                 debug=False) -> None:

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

        self.create_new_item = False
        self.json_representation = {}
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

        self.debug = debug

        if fast_run_case_insensitive and not self.search_only:
            raise ValueError("If using fast run case insensitive, search_only must be set")

        if self.ref_handler and not callable(self.ref_handler):
            raise TypeError("ref_handler must be callable")
        if self.global_ref_mode == 'CUSTOM' and self.ref_handler is None:
            raise ValueError("If using a custom ref mode, ref_handler must be set")

        if (core_props is None) and (self.sparql_endpoint_url not in ItemEngine.distinct_value_props):
            ItemEngine.distinct_value_props[self.sparql_endpoint_url] = wbi_functions.get_distinct_value_props(self.sparql_endpoint_url,
                                                                                                               self.wikibase_url,
                                                                                                               self.property_constraint_pid,
                                                                                                               self.distinct_values_constraint_qid)
        self.core_props = core_props if core_props is not None else ItemEngine.distinct_value_props[self.sparql_endpoint_url]

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

    def init_data_load(self):
        if self.item_id and self.item_data:
            if self.debug:
                print("Load item " + self.item_id + " from item_data")
            self.json_representation = self.parse_json(self.item_data)
        elif self.item_id:
            if self.debug:
                print("Load item " + self.item_id + " from MW API from item_id")
            self.json_representation = self.get_entity()
        else:
            if self.debug:
                print("Try to guess item QID from props")
            qids_by_props = ''
            try:
                qids_by_props = self.__select_item()
            except SearchError as e:
                print("ERROR init_data_load: " + str(e))

            if qids_by_props:
                self.item_id = qids_by_props
                if self.debug:
                    print("Item ID guessed is " + self.item_id)
                    print("Load item " + self.item_id + " from MW API")
                self.json_representation = self.get_entity()
                self.__check_integrity()

        if not self.search_only:
            self.__construct_claim_json()
        else:
            self.data = []

    def init_fastrun(self):
        # We search if we already have a FastRunContainer with the same parameters to re-use it
        for c in ItemEngine.fast_run_store:
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
            ItemEngine.fast_run_store.append(self.fast_run_container)

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

    def parse_json(self, json_data):
        """
        Parses an entity json and generates the datatype objects, sets self.json_representation

        :param json_data: the json of an entity
        :type json_data: A Python Json representation of an item
        :return: returns the json representation containing 'labels', 'descriptions', 'claims', 'aliases', 'sitelinks'.
        """

        data = {x: json_data[x] for x in ('labels', 'descriptions', 'claims', 'aliases') if x in json_data}
        data['sitelinks'] = {}
        self.entity_metadata = {x: json_data[x] for x in json_data if x not in ('labels', 'descriptions', 'claims', 'aliases', 'sitelinks')}
        self.sitelinks = json_data.get('sitelinks', {})

        self.statements = []
        for prop in data['claims']:
            for z in data['claims'][prop]:
                data_type = [x for x in BaseDataType.__subclasses__() if x.DTYPE == z['mainsnak']['datatype']][0]
                statement = data_type.from_json(z)
                self.statements.append(statement)

        self.json_representation = data
        self.original_statements = copy.deepcopy(self.statements)

        return data

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

    def get_entity(self):
        """
        retrieve an item in json representation from the Wikibase instance

        :rtype: dict
        :return: python complex dictionary representation of a json
        """

        params = {
            'action': 'wbgetentities',
            'sites': 'enwiki',
            'ids': self.item_id,
            'format': 'json'
        }

        json_data = wbi_functions.mediawiki_api_call_helper(data=params, allow_anonymous=True)
        return self.parse_json(json_data=json_data['entities'][self.item_id])

    def get_property_list(self):
        """
        List of properties on the current item

        :return: a list of property ID strings (Pxxxx).
        """

        property_list = set()
        for x in self.statements:
            property_list.add(x.get_prop_nr())

        return list(property_list)

    def get_json_representation(self):
        """
        A method to access the internal json representation of the item, mainly for testing

        :return: returns a Python json representation object of the item at the current state of the instance
        """

        return self.json_representation

    def get_label(self, lang=None):
        """
        Returns the label for a certain language

        :param lang:
        :type lang: str
        :return: returns the label in the specified language, an empty string if the label does not exist
        """

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if self.fast_run:
            return list(self.fast_run_container.get_language_data(self.item_id, lang, 'label'))[0]
        try:
            return self.json_representation['labels'][lang]['value']
        except KeyError:
            return ''

    def set_label(self, label, lang=None, if_exists='REPLACE'):
        """
        Set the label for an item in a certain language

        :param label: The label of the item in a certain language or None to remove the label in that language
        :type label: str or None
        :param lang: The language a label should be set for.
        :type lang: str
        :param if_exists: If a label already exist, 'REPLACE' it or 'KEEP' it
        :return: None
        """

        if self.search_only:
            raise SearchOnlyError

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if if_exists not in ('KEEP', 'REPLACE'):
            raise ValueError("{} is not a valid value for if_exists (REPLACE or KEEP)".format(if_exists))

        # Skip set_label if the item already have one and if_exists is at 'KEEP'
        if if_exists == 'KEEP':
            if lang in self.json_representation['labels']:
                return

            if self.fast_run_container and self.fast_run_container.get_language_data(self.item_id, lang, 'label') != ['']:
                return

        if self.fast_run and not self.require_write:
            self.require_write = self.fast_run_container.check_language_data(qid=self.item_id, lang_data=[label], lang=lang, lang_data_type='label')
            if self.require_write:
                self.init_data_load()
            else:
                return

        if 'labels' not in self.json_representation or not self.json_representation['labels']:
            self.json_representation['labels'] = {}

        if label is None:
            self.json_representation['labels'][lang] = {
                'language': lang,
                'remove': ''
            }
        else:
            self.json_representation['labels'][lang] = {
                'language': lang,
                'value': label
            }

    def get_aliases(self, lang=None):
        """
        Retrieve the aliases in a certain language

        :param lang: The language the description should be retrieved for
        :return: Returns a list of aliases, an empty list if none exist for the specified language
        """

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if self.fast_run:
            return list(self.fast_run_container.get_language_data(self.item_id, lang, 'aliases'))

        alias_list = []
        if 'aliases' in self.json_representation and lang in self.json_representation['aliases']:
            for alias in self.json_representation['aliases'][lang]:
                alias_list.append(alias['value'])

        return alias_list

    def set_aliases(self, aliases, lang=None, if_exists='APPEND'):
        """
        set the aliases for an item

        :param aliases: a string or a list of strings representing the aliases of an item
        :param lang: The language a description should be set for
        :param if_exists: If aliases already exist, APPEND or REPLACE
        :return: None
        """

        if self.search_only:
            raise SearchOnlyError

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if isinstance(aliases, str):
            aliases = [aliases]
        if not isinstance(aliases, list):
            raise TypeError("aliases must be a list or a string")

        if if_exists != 'APPEND' and if_exists != 'REPLACE':
            raise ValueError("{} is not a valid value for if_exists (REPLACE or APPEND)".format(if_exists))

        if self.fast_run and not self.require_write:
            self.require_write = self.fast_run_container.check_language_data(qid=self.item_id, lang_data=aliases, lang=lang, lang_data_type='aliases', if_exists=if_exists)
            if self.require_write:
                self.init_data_load()
            else:
                return

        if 'aliases' not in self.json_representation:
            self.json_representation['aliases'] = {}

        if if_exists == 'REPLACE' or lang not in self.json_representation['aliases']:
            self.json_representation['aliases'][lang] = []
            for alias in aliases:
                self.json_representation['aliases'][lang].append({
                    'language': lang,
                    'value': alias
                })
        else:
            for alias in aliases:
                found = False
                for current_aliases in self.json_representation['aliases'][lang]:
                    if alias.strip().casefold() != current_aliases['value'].strip().casefold():
                        continue
                    else:
                        found = True
                        break

                if not found:
                    self.json_representation['aliases'][lang].append({
                        'language': lang,
                        'value': alias
                    })

    def get_description(self, lang=None):
        """
        Retrieve the description in a certain language

        :param lang: The language the description should be retrieved for
        :return: Returns the description string
        """

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if self.fast_run:
            return list(self.fast_run_container.get_language_data(self.item_id, lang, 'description'))[0]
        if 'descriptions' not in self.json_representation or lang not in self.json_representation['descriptions']:
            return ''
        else:
            return self.json_representation['descriptions'][lang]['value']

    def set_description(self, description, lang=None, if_exists='REPLACE'):
        """
        Set the description for an item in a certain language

        :param description: The description of the item in a certain language
        :type description: str
        :param lang: The language a description should be set for.
        :type lang: str
        :param if_exists: If a description already exist, REPLACE it or KEEP it.
        :return: None
        """

        if self.search_only:
            raise SearchOnlyError

        lang = config['DEFAULT_LANGUAGE'] if lang is None else lang

        if if_exists != 'KEEP' and if_exists != 'REPLACE':
            raise ValueError("{} is not a valid value for if_exists (REPLACE or KEEP)".format(if_exists))

        # Skip set_description if the item already have one and if_exists is at 'KEEP'
        if if_exists == 'KEEP':
            if self.get_description(lang):
                return

            if self.fast_run_container and self.fast_run_container.get_language_data(self.item_id, lang, 'description') != ['']:
                return

        if self.fast_run and not self.require_write:
            self.require_write = self.fast_run_container.check_language_data(qid=self.item_id, lang_data=[description], lang=lang, lang_data_type='description')
            if self.require_write:
                self.init_data_load()
            else:
                return

        if 'descriptions' not in self.json_representation or not self.json_representation['descriptions']:
            self.json_representation['descriptions'] = {}

        self.json_representation['descriptions'][lang] = {
            'language': lang,
            'value': description
        }

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

    def write(self, login, bot_account=True, edit_summary='', entity_type='item', property_datatype='string', max_retries=1000, retry_after=60, all_claims=False,
              allow_anonymous=False):
        """
        Writes the item Json to the Wikibase instance and after successful write, updates the object with new ids and hashes generated by the Wikibase instance.
        For new items, also returns the new QIDs.

        :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
        :param bot_account: Tell the Wikidata API whether the script should be run as part of a bot account or not.
        :type bot_account: bool
        :param edit_summary: A short (max 250 characters) summary of the purpose of the edit. This will be displayed as the revision summary of the item.
        :type edit_summary: str
        :param entity_type: Decides wether the object will become a 'form', 'item' (default), 'lexeme', 'property' or 'sense'
        :type entity_type: str
        :param property_datatype: When payload_type is 'property' then this parameter set the datatype for the property
        :type property_datatype: str
        :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to `max_retries` times
        :type max_retries: int
        :param retry_after: Number of seconds to wait before retrying request (see max_retries)
        :type retry_after: int
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        :return: the entity ID on successful write
        """

        if self.search_only:
            raise SearchOnlyError

        if not self.require_write:
            return self.item_id

        if entity_type == 'property':
            self.json_representation['datatype'] = property_datatype
            if 'sitelinks' in self.json_representation:
                del self.json_representation['sitelinks']

        if all_claims:
            data = json.JSONEncoder().encode(self.json_representation)
        else:
            new_json_repr = {k: self.json_representation[k] for k in set(list(self.json_representation.keys())) - {'claims'}}
            new_json_repr['claims'] = {}
            for claim in self.json_representation['claims']:
                if [True for x in self.json_representation['claims'][claim] if 'id' not in x or 'remove' in x]:
                    new_json_repr['claims'][claim] = copy.deepcopy(self.json_representation['claims'][claim])
                    for statement in new_json_repr['claims'][claim]:
                        if 'id' in statement and 'remove' not in statement:
                            new_json_repr['claims'][claim].remove(statement)
                    if not new_json_repr['claims'][claim]:
                        new_json_repr['claims'].pop(claim)
            data = json.JSONEncoder().encode(new_json_repr)

        payload = {
            'action': 'wbeditentity',
            'data': data,
            'format': 'json',
            'token': login.get_edit_token(),
            'summary': edit_summary
        }

        if config['MAXLAG'] > 0:
            payload.update({'maxlag': config['MAXLAG']})

        if bot_account:
            payload.update({'bot': ''})

        if self.create_new_item:
            payload.update({u'new': entity_type})
        else:
            payload.update({u'id': self.item_id})

        if self.debug:
            print(payload)

        try:
            json_data = wbi_functions.mediawiki_api_call_helper(data=payload, login=login, max_retries=max_retries, retry_after=retry_after, allow_anonymous=allow_anonymous)

            if 'error' in json_data and 'messages' in json_data['error']:
                error_msg_names = set(x.get('name') for x in json_data['error']['messages'])
                if 'wikibase-validator-label-with-description-conflict' in error_msg_names:
                    raise NonUniqueLabelDescriptionPairError(json_data)
                else:
                    raise MWApiError(json_data)
            elif 'error' in json_data.keys():
                raise MWApiError(json_data)
        except Exception:
            print('Error while writing to the Wikibase instance')
            raise

        # after successful write, update this object with latest json, QID and parsed data types.
        self.create_new_item = False
        self.item_id = json_data['entity']['id']
        self.parse_json(json_data=json_data['entity'])
        self.data = []
        if 'success' in json_data and 'entity' in json_data and 'lastrevid' in json_data['entity']:
            self.lastrevid = json_data['entity']['lastrevid']
        return self.item_id

    def __check_integrity(self):
        """
        A method to check if when invoking __select_item() and the item does not exist yet, but another item
        has a property of the current domain with a value like submitted in the data dict, this item does not get
        selected but a ManualInterventionReqException() is raised. This check is dependent on the core identifiers
        of a certain domain.

        :return: boolean True if test passed
        """

        # all core props
        wbi_core_props = self.core_props
        # core prop statements that exist on the item
        cp_statements = [x for x in self.statements if x.get_prop_nr() in wbi_core_props]
        item_core_props = set(x.get_prop_nr() for x in cp_statements)
        # core prop statements we are loading
        cp_data = [x for x in self.data if x.get_prop_nr() in wbi_core_props]

        # compare the claim values of the currently loaded QIDs to the data provided in self.data
        # this is the number of core_ids in self.data that are also on the item
        count_existing_ids = len([x for x in self.data if x.get_prop_nr() in item_core_props])

        core_prop_match_count = 0
        for new_stat in self.data:
            for stat in self.statements:
                if (new_stat.get_prop_nr() == stat.get_prop_nr()) and (new_stat.get_value() == stat.get_value()) and (
                        new_stat.get_prop_nr() in item_core_props):
                    core_prop_match_count += 1

        if core_prop_match_count < count_existing_ids * self.core_prop_match_thresh:
            existing_core_pv = defaultdict(set)
            for s in cp_statements:
                existing_core_pv[s.get_prop_nr()].add(s.get_value())
            new_core_pv = defaultdict(set)
            for s in cp_data:
                new_core_pv[s.get_prop_nr()].add(s.get_value())
            nomatch_existing = {k: v - new_core_pv[k] for k, v in existing_core_pv.items()}
            nomatch_existing = {k: v for k, v in nomatch_existing.items() if v}
            nomatch_new = {k: v - existing_core_pv[k] for k, v in new_core_pv.items()}
            nomatch_new = {k: v for k, v in nomatch_new.items() if v}
            raise CorePropIntegrityException("Retrieved item ({}) does not match provided core IDs. "
                                             "Matching count {}, non-matching count {}. "
                                             .format(self.item_id, core_prop_match_count,
                                                     count_existing_ids - core_prop_match_count) +
                                             "existing unmatched core props: {}. ".format(nomatch_existing) +
                                             "statement unmatched core props: {}.".format(nomatch_new))
        else:
            return True

    def __select_item(self):
        """
        The most likely item QID should be returned, after querying the Wikibase instance for all values in core_id properties

        :return: Either a single QID is returned, or an empty string if no suitable item in the Wikibase instance
        """

        qid_list = set()
        conflict_source = {}

        for statement in self.data:
            property_nr = statement.get_prop_nr()

            core_props = self.core_props
            if property_nr in core_props:
                tmp_qids = set()
                query = statement.sparql_query.format(wb_url=self.wikibase_url, pid=property_nr, value=str(statement.get_sparql_value()).replace("'", r"\'"))
                results = wbi_functions.execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url, debug=self.debug)

                for i in results['results']['bindings']:
                    qid = i['item_id']['value'].split('/')[-1]
                    tmp_qids.add(qid)

                qid_list.update(tmp_qids)

                # Protocol in what property the conflict arises
                if property_nr in conflict_source:
                    conflict_source[property_nr].append(tmp_qids)
                else:
                    conflict_source[property_nr] = [tmp_qids]

                if len(tmp_qids) > 1:
                    raise ManualInterventionReqException("More than one item has the same property value", property_nr, tmp_qids)

        if len(qid_list) == 0:
            self.create_new_item = True
            return ''

        if self.debug:
            print(qid_list)

        unique_qids = set(qid_list)
        if len(unique_qids) > 1:
            raise ManualInterventionReqException("More than one item has the same property value", conflict_source, unique_qids)
        elif len(unique_qids) == 1:
            return list(unique_qids)[0]

    def __construct_claim_json(self):
        """
        Writes the properties from self.data to a new or existing json in self.json_representation

        :return: None
        """

        def handle_qualifiers(old_item, new_item):
            if not new_item.check_qualifier_equality:
                old_item.set_qualifiers(new_item.get_qualifiers())

        def is_good_ref(ref_block):
            prop_nrs = [x.get_prop_nr() for x in ref_block]
            values = [x.get_value() for x in ref_block]
            good_ref = True
            prop_value_map = dict(zip(prop_nrs, values))

            # if self.good_refs has content, use these to determine good references
            if self.good_refs and len(self.good_refs) > 0:
                found_good = True
                for rblock in self.good_refs:

                    if not all([k in prop_value_map for k, v in rblock.items()]):
                        found_good = False

                    if not all([v in prop_value_map[k] for k, v in rblock.items() if v]):
                        found_good = False

                    if found_good:
                        return True

                return False

            return good_ref

        def handle_references(old_item, new_item):
            """
            Local function to handle references

            :param old_item: An item containing the data as currently in the Wikibase instance
            :type old_item: A child of BaseDataType
            :param new_item: An item containing the new data which should be written to the Wikibase instance
            :type new_item: A child of BaseDataType
            """

            old_references = old_item.get_references()
            new_references = new_item.get_references()

            if sum(map(lambda z: len(z), old_references)) == 0 or self.global_ref_mode == 'STRICT_OVERWRITE':
                old_item.set_references(new_references)

            elif self.global_ref_mode == 'STRICT_KEEP' or new_item.statement_ref_mode == 'STRICT_KEEP':
                pass

            elif self.global_ref_mode == 'STRICT_KEEP_APPEND' or new_item.statement_ref_mode == 'STRICT_KEEP_APPEND':
                old_references.extend(new_references)
                old_item.set_references(old_references)

            elif self.global_ref_mode == 'CUSTOM' or new_item.statement_ref_mode == 'CUSTOM' and self.ref_handler and callable(self.ref_handler):
                self.ref_handler(old_item, new_item)

            elif self.global_ref_mode == 'KEEP_GOOD' or new_item.statement_ref_mode == 'KEEP_GOOD':
                # Copy only good_ref
                refs = [x for x in old_references if is_good_ref(x)]

                # Don't add already existing references
                for new_ref in new_references:
                    if new_ref not in old_references:
                        refs.append(new_ref)

                # Set the references
                old_item.set_references(refs)

        # sort the incoming data according to the property number
        self.data.sort(key=lambda z: z.get_prop_nr().lower())

        # collect all statements which should be deleted because of an empty value
        statements_for_deletion = []
        for item in self.data:
            if isinstance(item, BaseDataType) and item.get_value() == '':
                statements_for_deletion.append(item.get_prop_nr())

        if self.create_new_item:
            self.statements = copy.copy(self.data)
        else:
            for stat in self.data:
                prop_nr = stat.get_prop_nr()

                prop_data = [x for x in self.statements if x.get_prop_nr() == prop_nr]
                if prop_data and stat.if_exists == 'KEEP':
                    continue
                prop_pos = [x.get_prop_nr() == prop_nr for x in self.statements]
                prop_pos.reverse()
                insert_pos = len(prop_pos) - (prop_pos.index(True) if any(prop_pos) else 0)

                # If value should be appended, check if values exists, if not, append
                if 'APPEND' in stat.if_exists:
                    equal_items = [stat == x for x in prop_data]
                    if True not in equal_items or stat.if_exists == 'FORCE_APPEND':
                        self.statements.insert(insert_pos + 1, stat)
                    else:
                        # if item exists, modify rank
                        current_item = prop_data[equal_items.index(True)]
                        current_item.set_rank(stat.get_rank())
                        handle_references(old_item=current_item, new_item=stat)
                        handle_qualifiers(old_item=current_item, new_item=stat)
                    continue

                # set all existing values of a property for removal
                for x in prop_data:
                    # for deletion of single statements, do not set all others to delete
                    if hasattr(stat, 'remove'):
                        break
                    elif x.get_id() and not hasattr(x, 'retain'):
                        # keep statements with good references if keep_good_ref_statements is True
                        if self.keep_good_ref_statements:
                            if any([is_good_ref(r) for r in x.get_references()]):
                                setattr(x, 'retain', '')
                        else:
                            setattr(x, 'remove', '')

                match = []
                for i in prop_data:
                    if stat == i and hasattr(stat, 'remove'):
                        match.append(True)
                        setattr(i, 'remove', '')
                    elif stat == i:
                        match.append(True)
                        setattr(i, 'retain', '')
                        if hasattr(i, 'remove'):
                            delattr(i, 'remove')
                        handle_references(old_item=i, new_item=stat)
                        handle_qualifiers(old_item=i, new_item=stat)

                        i.set_rank(rank=stat.get_rank())
                    # if there is no value, do not add an element, this is also used to delete whole properties.
                    elif i.get_value():
                        match.append(False)

                if True not in match and not hasattr(stat, 'remove'):
                    self.statements.insert(insert_pos + 1, stat)

        # For whole property deletions, add remove flag to all statements which should be deleted
        for item in copy.deepcopy(self.statements):
            if item.get_prop_nr() in statements_for_deletion:
                if item.get_id() != '':
                    setattr(item, 'remove', '')
                else:
                    self.statements.remove(item)

        # regenerate claim json
        self.json_representation['claims'] = {}
        for stat in self.statements:
            prop_nr = stat.get_prop_nr()
            if prop_nr not in self.json_representation['claims']:
                self.json_representation['claims'][prop_nr] = []
            self.json_representation['claims'][prop_nr].append(stat.get_json_representation())

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
