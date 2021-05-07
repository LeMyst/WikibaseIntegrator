import copy
import datetime
import json
import re
from collections import defaultdict
from time import sleep
from warnings import warn

import pandas
import requests

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_backoff import wbi_backoff
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_fastrun import FastRunContainer


class ItemEngine(object):
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
            ItemEngine.distinct_value_props[self.sparql_endpoint_url] = FunctionsEngine.get_distinct_value_props(self.sparql_endpoint_url,
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

        json_data = FunctionsEngine.mediawiki_api_call_helper(data=params, allow_anonymous=True)
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

        if 'descriptions' not in self.json_representation or not self.json_representation['descriptions'] or if_exists == 'REPLACE':
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
            json_data = FunctionsEngine.mediawiki_api_call_helper(data=payload, login=login, max_retries=max_retries, retry_after=retry_after, allow_anonymous=allow_anonymous)

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
                query = statement.sparql_query.format(wb_url=self.wikibase_url, pid=property_nr, value=statement.get_sparql_value().replace("'", r"\'"))
                results = FunctionsEngine.execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url, debug=self.debug)

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


class FunctionsEngine(object):

    @staticmethod
    def mediawiki_api_call(method, mediawiki_api_url=None, session=None, max_retries=1000, retry_after=60, **kwargs):
        """
        :param method: 'GET' or 'POST'
        :param mediawiki_api_url:
        :param session: If a session is passed, it will be used. Otherwise a new requests session is created
        :param max_retries: If api request fails due to rate limiting, maxlag, or readonly mode, retry up to
        `max_retries` times
        :type max_retries: int
        :param retry_after: Number of seconds to wait before retrying request (see max_retries)
        :type retry_after: int
        :param kwargs: Passed to requests.request
        :return:
        """

        mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url

        # TODO: Add support for 'multipart/form-data' when using POST (https://www.mediawiki.org/wiki/API:Edit#Large_edits)

        response = None
        session = session if session else requests.session()
        for n in range(max_retries):
            try:
                response = session.request(method, mediawiki_api_url, **kwargs)
            except requests.exceptions.ConnectionError as e:
                print("Connection error: {}. Sleeping for {} seconds.".format(e, retry_after))
                sleep(retry_after)
                continue
            if response.status_code == 503:
                print("service unavailable. sleeping for {} seconds".format(retry_after))
                sleep(retry_after)
                continue

            response.raise_for_status()
            json_data = response.json()
            """
            Mediawiki api response has code = 200 even if there are errors.
            rate limit doesn't return HTTP 429 either. may in the future
            https://phabricator.wikimedia.org/T172293
            """
            if 'error' in json_data:
                # rate limiting
                error_msg_names = set()
                if 'messages' in json_data['error']:
                    error_msg_names = set(x.get('name') for x in json_data['error']['messages'])
                if 'actionthrottledtext' in error_msg_names:
                    sleep_sec = int(response.headers.get('retry-after', retry_after))
                    print("{}: rate limited. sleeping for {} seconds".format(datetime.datetime.utcnow(), sleep_sec))
                    sleep(sleep_sec)
                    continue

                # maxlag
                if 'code' in json_data['error'] and json_data['error']['code'] == 'maxlag':
                    sleep_sec = json_data['error'].get('lag', retry_after)
                    print("{}: maxlag. sleeping for {} seconds".format(datetime.datetime.utcnow(), sleep_sec))
                    sleep(sleep_sec)
                    continue

                # readonly
                if 'code' in json_data['error'] and json_data['error']['code'] == 'readonly':
                    print('The Wikibase instance is currently in readonly mode, waiting for {} seconds'.format(retry_after))
                    sleep(retry_after)
                    continue

                # others case
                raise MWApiError(response.json() if response else {})

            # there is no error or waiting. break out of this loop and parse response
            break
        else:
            # the first time I've ever used for - else!!
            # else executes if the for loop completes normally. i.e. does not encouter a `break`
            # in this case, that means it tried this api call 10 times
            raise MWApiError(response.json() if response else {})

        return json_data

    @staticmethod
    def mediawiki_api_call_helper(data, login=None, mediawiki_api_url=None, user_agent=None, allow_anonymous=False, max_retries=1000, retry_after=60):
        mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
        user_agent = config['USER_AGENT_DEFAULT'] if user_agent is None else user_agent

        if not allow_anonymous:
            if login is None:
                # Force allow_anonymous as False by default to ask for a login object
                raise ValueError("allow_anonymous can't be False and login is None at the same time.")
            elif mediawiki_api_url != login.mediawiki_api_url:
                raise ValueError("mediawiki_api_url can't be different with the one in the login object.")

        headers = {
            'User-Agent': user_agent
        }

        if data is not None:
            # format can only be json when using mediawiki_api_call()
            if 'format' not in data:
                data.update({'format': 'json'})

            if login is not None and 'token' not in data:
                data.update({'token': login.get_edit_token()})

            if not allow_anonymous:
                # Always assert user if allow_anonymous is False
                if 'assert' not in data:
                    data.update({'assert': 'user'})
                if 'token' in data and data['token'] == '+\\':
                    raise wbi_login.LoginError("Anonymous edit are not allowed by default. Set allow_anonymous to True to edit mediawiki anonymously.")
            elif 'assert' not in data:
                # Always assert anon if allow_anonymous is True
                data.update({'assert': 'anon'})

        login_session = login.get_session() if login is not None else None

        return FunctionsEngine.mediawiki_api_call('POST', mediawiki_api_url, login_session, data=data, headers=headers, max_retries=max_retries, retry_after=retry_after)

    @staticmethod
    @wbi_backoff()
    def execute_sparql_query(query, prefix=None, endpoint=None, user_agent=None, as_dataframe=False, max_retries=1000, retry_after=60, debug=False):
        """
        Static method which can be used to execute any SPARQL query
        :param prefix: The URI prefixes required for an endpoint, default is the Wikidata specific prefixes
        :param query: The actual SPARQL query string
        :param endpoint: The URL string for the SPARQL endpoint. Default is the URL for the Wikidata SPARQL endpoint
        :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
        :type user_agent: str
        :param as_dataframe: Return result as pandas dataframe
        :param max_retries: The number time this function should retry in case of header reports.
        :param retry_after: the number of seconds should wait upon receiving either an error code or the Query Service is not reachable.
        :param debug: Enable debug output.
        :type debug: boolean
        :return: The results of the query are returned in JSON format
        """

        sparql_endpoint_url = config['SPARQL_ENDPOINT_URL'] if endpoint is None else endpoint
        user_agent = config['USER_AGENT_DEFAULT'] if user_agent is None else user_agent

        if prefix:
            query = prefix + '\n' + query

        params = {
            'query': '#Tool: wbi_core execute_sparql_query\n' + query,
            'format': 'json'
        }

        headers = {
            'Accept': 'application/sparql-results+json',
            'User-Agent': user_agent
        }

        if debug:
            print(params['query'])

        for n in range(max_retries):
            try:
                response = requests.post(sparql_endpoint_url, params=params, headers=headers)
            except requests.exceptions.ConnectionError as e:
                print("Connection error: {}. Sleeping for {} seconds.".format(e, retry_after))
                sleep(retry_after)
                continue
            if response.status_code == 503:
                print("Service unavailable (503). Sleeping for {} seconds".format(retry_after))
                sleep(retry_after)
                continue
            if response.status_code == 429:
                if 'retry-after' in response.headers.keys():
                    retry_after = response.headers['retry-after']
                print("Too Many Requests (429). Sleeping for {} seconds".format(retry_after))
                sleep(retry_after)
                continue
            response.raise_for_status()
            results = response.json()

            if as_dataframe:
                return FunctionsEngine._sparql_query_result_to_df(results)
            else:
                return results

    @staticmethod
    def _sparql_query_result_to_df(results):

        def parse_value(item):
            if item.get('datatype') == 'http://www.w3.org/2001/XMLSchema#decimal':
                return float(item['value'])
            if item.get('datatype') == 'http://www.w3.org/2001/XMLSchema#integer':
                return int(item['value'])
            if item.get('datatype') == 'http://www.w3.org/2001/XMLSchema#dateTime':
                return datetime.datetime.strptime(item['value'], '%Y-%m-%dT%H:%M:%SZ')
            return item['value']

        results = results['results']['bindings']
        results = [{k: parse_value(v) for k, v in item.items()} for item in results]
        df = pandas.DataFrame(results)
        return df

    @staticmethod
    def get_linked_by(qid, mediawiki_api_url=None):
        """
            :param qid: Wikidata identifier to which other wikidata items link
            :param mediawiki_api_url: default to wikidata's api, but can be changed to any Wikibase
            :return:
        """

        mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url

        linkedby = []
        whatlinkshere = json.loads(requests.get(mediawiki_api_url + '?action=query&list=backlinks&format=json&bllimit=500&bltitle=' + qid).text)
        for link in whatlinkshere['query']['backlinks']:
            if link['title'].startswith('Q'):
                linkedby.append(link['title'])
        while 'continue' in whatlinkshere.keys():
            whatlinkshere = json.loads(requests.get(mediawiki_api_url + '?action=query&list=backlinks&blcontinue=' +
                                                    whatlinkshere['continue']['blcontinue'] + '&format=json&bllimit=500&bltitle=' + qid).text)
            for link in whatlinkshere['query']['backlinks']:
                if link['title'].startswith('Q'):
                    linkedby.append(link['title'])
        return linkedby

    @staticmethod
    def merge_items(from_id, to_id, login, ignore_conflicts='', mediawiki_api_url=None, user_agent=None, allow_anonymous=False):
        """
        A static method to merge two items
        :param from_id: The QID which should be merged into another item
        :type from_id: string with 'Q' prefix
        :param to_id: The QID into which another item should be merged
        :type to_id: string with 'Q' prefix
        :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
        :param mediawiki_api_url: The MediaWiki url which should be used
        :type mediawiki_api_url: str
        :param ignore_conflicts: A string with the values 'description', 'statement' or 'sitelink', separated by a pipe ('|') if using more than one of those.
        :type ignore_conflicts: str
        :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
        :type user_agent: str
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        """

        params = {
            'action': 'wbmergeitems',
            'fromid': from_id,
            'toid': to_id,
            'token': login.get_edit_token(),
            'format': 'json',
            'bot': '',
            'ignoreconflicts': ignore_conflicts
        }

        if config['MAXLAG'] > 0:
            params.update({'maxlag': config['MAXLAG']})

        return FunctionsEngine.mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

    @staticmethod
    def delete_item(item, reason, login, mediawiki_api_url=None, user_agent=None, allow_anonymous=False):
        """
        Delete an item
        :param item: a QID which should be deleted
        :type item: string
        :param reason: short text about the reason for the deletion request
        :type reason: str
        :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
        :param mediawiki_api_url: The MediaWiki url which should be used
        :type mediawiki_api_url: str
        :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
        :type user_agent: str
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        """

        params = {
            'action': 'delete',
            'title': 'Item:' + item,
            'reason': reason,
            'token': login.get_edit_token(),
            'format': 'json'
        }

        if config['MAXLAG'] > 0:
            params.update({'maxlag': config['MAXLAG']})

        return FunctionsEngine.mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

    @staticmethod
    def delete_statement(statement_id, revision, login, mediawiki_api_url=None, user_agent=None, allow_anonymous=False):
        """
        Delete an item
        :param statement_id: One GUID or several (pipe-separated) GUIDs identifying the claims to be removed. All claims must belong to the same entity.
        :type statement_id: string
        :param revision: The numeric identifier for the revision to base the modification on. This is used for detecting conflicts during save.
        :type revision: str
        :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
        :param mediawiki_api_url: The MediaWiki url which should be used
        :type mediawiki_api_url: str
        :param user_agent: Set a user agent string for the HTTP header to let the Query Service know who you are.
        :type user_agent: str
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        """

        params = {
            'action': 'wbremoveclaims',
            'claim': statement_id,
            'token': login.get_edit_token(),
            'baserevid': revision,
            'bot': True,
            'format': 'json'
        }

        if config['MAXLAG'] > 0:
            params.update({'maxlag': config['MAXLAG']})

        return FunctionsEngine.mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

    @staticmethod
    def get_search_results(search_string='', search_type='item', mediawiki_api_url=None, user_agent=None, max_results=500, language=None, dict_result=False, allow_anonymous=True):
        """
        Performs a search for entities in the Wikibase instance using labels and aliases.
        :param search_string: a string which should be searched for in the Wikibase instance (labels and aliases)
        :type search_string: str
        :param search_type: Search for this type of entity. One of the following values: form, item, lexeme, property, sense
        :type search_type: str
        :param mediawiki_api_url: Specify the mediawiki_api_url.
        :type mediawiki_api_url: str
        :param user_agent: The user agent string transmitted in the http header
        :type user_agent: str
        :param max_results: The maximum number of search results returned. Default 500
        :type max_results: int
        :param language: The language in which to perform the search.
        :type language: str
        :param dict_result:
        :type dict_result: boolean
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        :return: list
        """

        language = config['DEFAULT_LANGUAGE'] if language is None else language

        params = {
            'action': 'wbsearchentities',
            'language': language,
            'search': search_string,
            'type': search_type,
            'format': 'json',
            'limit': 50
        }

        cont_count = 0
        results = []

        while True:
            params.update({'continue': cont_count})

            search_results = FunctionsEngine.mediawiki_api_call_helper(data=params, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

            if search_results['success'] != 1:
                raise SearchError('Wikibase API wbsearchentities failed')
            else:
                for i in search_results['search']:
                    if dict_result:
                        description = i['description'] if 'description' in i else None
                        aliases = i['aliases'] if 'aliases' in i else None
                        results.append({
                            'id': i['id'],
                            'label': i['label'],
                            'match': i['match'],
                            'description': description,
                            'aliases': aliases
                        })
                    else:
                        results.append(i['id'])

            if 'search-continue' not in search_results:
                break
            else:
                cont_count = search_results['search-continue']

            if cont_count >= max_results:
                break

        return results

    @staticmethod
    def generate_item_instances(items, mediawiki_api_url=None, login=None, user_agent=None, allow_anonymous=True):
        """
        A method which allows for retrieval of a list of Wikidata items or properties. The method generates a list of
        tuples where the first value in the tuple is the QID or property ID, whereas the second is the new instance of
        ItemEngine containing all the data of the item. This is most useful for mass retrieval of items.
        :param user_agent: A custom user agent
        :type user_agent: str
        :param items: A list of QIDs or property IDs
        :type items: list
        :param mediawiki_api_url: The MediaWiki url which should be used
        :type mediawiki_api_url: str
        :param login: The object containing the login credentials and cookies. An instance of wbi_login.Login.
        :return: A list of tuples, first value in the tuple is the QID or property ID string, second value is the instance of ItemEngine with the corresponding
            item data.
        :param allow_anonymous: Allow anonymous edit to the MediaWiki API. Disabled by default.
        :type allow_anonymous: bool
        """

        assert type(items) == list

        params = {
            'action': 'wbgetentities',
            'ids': '|'.join(items),
            'format': 'json'
        }

        reply = FunctionsEngine.mediawiki_api_call_helper(data=params, login=login, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent, allow_anonymous=allow_anonymous)

        item_instances = []
        for qid, v in reply['entities'].items():
            ii = ItemEngine(item_id=qid, item_data=v)
            ii.mediawiki_api_url = mediawiki_api_url
            item_instances.append((qid, ii))

        return item_instances

    @staticmethod
    def get_distinct_value_props(sparql_endpoint_url=None, wikibase_url=None, property_constraint_pid=None,
                                 distinct_values_constraint_qid=None):
        """
        On wikidata, the default core IDs will be the properties with a distinct values constraint select ?p where {?p wdt:P2302 wd:Q21502410}
        See: https://www.wikidata.org/wiki/Help:Property_constraints_portal
        https://www.wikidata.org/wiki/Help:Property_constraints_portal/Unique_value
        """

        wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url
        property_constraint_pid = config['PROPERTY_CONSTRAINT_PID'] if property_constraint_pid is None else property_constraint_pid
        distinct_values_constraint_qid = config['DISTINCT_VALUES_CONSTRAINT_QID'] if distinct_values_constraint_qid is None else distinct_values_constraint_qid

        pcpid = property_constraint_pid
        dvcqid = distinct_values_constraint_qid

        query = '''
        SELECT ?p WHERE {{
            ?p <{wb_url}/prop/direct/{prop_nr}> <{wb_url}/entity/{entity}>
        }}
        '''.format(wb_url=wikibase_url, prop_nr=pcpid, entity=dvcqid)
        df = FunctionsEngine.execute_sparql_query(query, endpoint=sparql_endpoint_url, as_dataframe=True)
        if df.empty:
            warn("Warning: No distinct value properties found\n" +
                 "Please set P2302 and Q21502410 in your Wikibase or set `core_props` manually.\n" +
                 "Continuing with no core_props")
            return set()
        else:
            df.p = df.p.str.rsplit('/', 1).str[-1]
            return set(df.p)


class JsonParser(object):
    references = []
    qualifiers = []
    final = False
    current_type = None

    def __init__(self, f):
        self.f = f

    def __call__(self, *args):
        self.json_representation = args[1]

        if self.final:
            self.final = False
            return self.f(cls=self.current_type, jsn=self.json_representation)

        if 'mainsnak' in self.json_representation:
            self.mainsnak = None
            self.references = []
            self.qualifiers = []
            json_representation = self.json_representation

            if 'references' in json_representation:
                self.references.extend([[] for _ in json_representation['references']])
                for count, ref_block in enumerate(json_representation['references']):
                    ref_hash = ''
                    if 'hash' in ref_block:
                        ref_hash = ref_block['hash']
                    for prop in ref_block['snaks-order']:
                        jsn = ref_block['snaks'][prop]

                        for prop_ref in jsn:
                            ref_class = self.get_class_representation(prop_ref)
                            ref_class.is_reference = True
                            ref_class.snak_type = prop_ref['snaktype']
                            ref_class.set_hash(ref_hash)

                            self.references[count].append(copy.deepcopy(ref_class))

                            # print(self.references)
            if 'qualifiers' in json_representation:
                for prop in json_representation['qualifiers-order']:
                    for qual in json_representation['qualifiers'][prop]:
                        qual_hash = ''
                        if 'hash' in qual:
                            qual_hash = qual['hash']

                        qual_class = self.get_class_representation(qual)
                        qual_class.is_qualifier = True
                        qual_class.snak_type = qual['snaktype']
                        qual_class.set_hash(qual_hash)
                        self.qualifiers.append(qual_class)

                        # print(self.qualifiers)
            mainsnak = self.get_class_representation(json_representation['mainsnak'])
            mainsnak.set_references(self.references)
            mainsnak.set_qualifiers(self.qualifiers)
            if 'id' in json_representation:
                mainsnak.set_id(json_representation['id'])
            if 'rank' in json_representation:
                mainsnak.set_rank(json_representation['rank'])
            mainsnak.snak_type = json_representation['mainsnak']['snaktype']

            return mainsnak

        elif 'property' in self.json_representation:
            return self.get_class_representation(jsn=self.json_representation)

    def get_class_representation(self, jsn):
        data_type = [x for x in BaseDataType.__subclasses__() if x.DTYPE == jsn['datatype']][0]
        self.final = True
        self.current_type = data_type
        return data_type.from_json(jsn)


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
        :type time: str in the format '+%Y-%m-%dT%H:%M:%SZ', e.g. '+2001-12-31T12:01:13Z'
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


class MusicalNotation(BaseDataType):
    """
    Implements the Wikibase data type 'string'
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


class MWApiError(Exception):
    def __init__(self, error_message):
        """
        Base class for Mediawiki API error handling
        :param error_message: The error message returned by the Mediawiki API
        :type error_message: A Python json representation dictionary of the error message
        :return:
        """
        self.error_msg = error_message

    def __str__(self):
        return repr(self.error_msg)


class NonUniqueLabelDescriptionPairError(MWApiError):
    def __init__(self, error_message):
        """
        This class handles errors returned from the API due to an attempt to create an item which has the same
         label and description as an existing item in a certain language.
        :param error_message: An API error message containing 'wikibase-validator-label-with-description-conflict'
         as the message name.
        :type error_message: A Python json representation dictionary of the error message
        :return:
        """
        self.error_msg = error_message

    def get_language(self):
        """
        :return: Returns a 2 letter language string, indicating the language which triggered the error
        """
        return self.error_msg['error']['messages'][0]['parameters'][1]

    def get_conflicting_item_qid(self):
        """
        :return: Returns the QID string of the item which has the same label and description as the one which should
         be set.
        """
        qid_string = self.error_msg['error']['messages'][0]['parameters'][2]

        return qid_string.split('|')[0][2:]

    def __str__(self):
        return repr(self.error_msg)


class IDMissingError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class SearchError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class ManualInterventionReqException(Exception):
    def __init__(self, value, property_string, item_list):
        self.value = value + ' Property: {}, items affected: {}'.format(property_string, item_list)

    def __str__(self):
        return repr(self.value)


class CorePropIntegrityException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class MergeError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class SearchOnlyError(Exception):
    """Raised when the ItemEngine is in search_only mode"""
    pass
