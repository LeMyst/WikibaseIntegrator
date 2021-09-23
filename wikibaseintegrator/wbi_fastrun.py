from __future__ import annotations

import collections
import copy
from collections import defaultdict
from functools import lru_cache, wraps
from itertools import chain
from typing import TYPE_CHECKING, Dict, List, Optional, Type, Union

from frozendict import frozendict

from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_helpers import execute_sparql_query, format_amount

if TYPE_CHECKING:
    from wikibaseintegrator.models import Claim, Claims

fastrun_store: List[FastRunContainer] = []


class FastRunContainer:
    def __init__(self, base_data_type: Type[BaseDataType], mediawiki_api_url: str = None, sparql_endpoint_url: str = None, wikibase_url: str = None, base_filter: Dict = None,
                 use_refs: bool = False, case_insensitive: bool = False, debug: bool = None):
        self.reconstructed_statements: List[BaseDataType] = []
        self.rev_lookup: defaultdict[str, set] = defaultdict(set)
        self.rev_lookup_ci: defaultdict[str, set] = defaultdict(set)
        self.prop_data: Dict[str, dict] = {}
        self.loaded_langs: Dict[str, dict] = {}
        self.base_filter = {}
        self.base_filter_string = ''
        self.prop_dt_map: Dict[str, str] = {}
        self.current_qid = ''

        self.base_data_type = base_data_type
        self.mediawiki_api_url = mediawiki_api_url or config['MEDIAWIKI_API_URL']
        self.sparql_endpoint_url = sparql_endpoint_url or config['SPARQL_ENDPOINT_URL']
        self.wikibase_url = wikibase_url or config['WIKIBASE_URL']
        self.use_refs = use_refs
        self.case_insensitive = case_insensitive

        self.debug = debug or config['DEBUG']

        if base_filter and any(base_filter):
            self.base_filter = base_filter
            for k, v in self.base_filter.items():
                ks = []
                if k.count('/') == 1:
                    ks = k.split('/')
                if v:
                    if ks:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* ' \
                                                   '<{wb_url}/entity/{entity}> .\n'.format(wb_url=self.wikibase_url, prop_nr1=ks[0], prop_nr2=ks[1], entity=v)
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> <{wb_url}/entity/{entity}> .\n'.format(wb_url=self.wikibase_url,
                                                                                                                                  prop_nr=k, entity=v)
                else:
                    if ks:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* ' \
                                                   '?zz{prop_nr1}{prop_nr2} .\n'.format(wb_url=self.wikibase_url, prop_nr1=ks[0], prop_nr2=ks[1])
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> ?zz{prop_nr} .\n'.format(wb_url=self.wikibase_url, prop_nr=k)

    def reconstruct_statements(self, qid: str) -> List[BaseDataType]:
        reconstructed_statements: List[BaseDataType] = []

        if qid not in self.prop_data:
            self.reconstructed_statements = reconstructed_statements
            return reconstructed_statements

        for prop_nr, dt in self.prop_data[qid].items():
            # get datatypes for qualifier props
            q_props = set(chain(*([x[0] for x in d['qual']] for d in dt.values())))
            r_props = set(chain(*(set(chain(*([y[0] for y in x] for x in d['ref'].values()))) for d in dt.values())))
            props = q_props | r_props
            for prop in props:
                if prop not in self.prop_dt_map:
                    self.prop_dt_map.update({prop: self.get_prop_datatype(prop)})
            # reconstruct statements from frc (including unit, qualifiers, and refs)
            for uid, d in dt.items():
                qualifiers = []
                for q in d['qual']:
                    f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[q[0]]][0]
                    # TODO: Add support for more data type (Time, MonolingualText, GlobeCoordinate)
                    if self.prop_dt_map[q[0]] == 'quantity':
                        qualifiers.append(f(value=q[1], prop_nr=q[0], is_qualifier=True, unit=q[2]))
                    else:
                        qualifiers.append(f(value=q[1], prop_nr=q[0], is_qualifier=True))

                references = []
                for ref_id, refs in d['ref'].items():
                    this_ref = []
                    for ref in refs:
                        f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[ref[0]]][0]
                        this_ref.append(f(value=ref[1], prop_nr=ref[0]))
                    references.append(this_ref)

                f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[prop_nr]][0]
                # TODO: Add support for more data type
                if self.prop_dt_map[prop_nr] == 'quantity':
                    reconstructed_statements.append(f(value=d['v'], prop_nr=prop_nr, qualifiers=qualifiers, references=references, unit=d['unit']))
                else:
                    reconstructed_statements.append(f(value=d['v'], prop_nr=prop_nr, qualifiers=qualifiers, references=references))

        # this isn't used. done for debugging purposes
        self.reconstructed_statements = reconstructed_statements
        return reconstructed_statements

    def get_item(self, claims: List, cqid: str = None) -> str:
        self.load_item(claims=claims, cqid=cqid)
        return self.current_qid

    def load_item(self, claims: Union[list, Claims], cqid: str = None) -> bool:
        match_sets = []
        for claim in claims:
            # skip to next if statement has no value or no data type defined, e.g. for deletion objects
            if not claim.mainsnak.datavalue and not claim.datatype:
                continue

            prop_nr = claim.mainsnak.property_number

            if prop_nr not in self.prop_dt_map:
                if self.debug:
                    print(f"{prop_nr} not found in fastrun")
                self.prop_dt_map.update({prop_nr: self.get_prop_datatype(prop_nr)})
                self._query_data(prop_nr=prop_nr, use_units=claim.mainsnak.datatype == 'quantity')

            current_value = claim.get_sparql_value()

            if self.prop_dt_map[prop_nr] == 'wikibase-item':
                if not str(current_value).startswith('Q'):
                    current_value = f'Q{current_value}'

            if self.debug:
                print(current_value)
                if self.case_insensitive:
                    print("case insensitive enabled")
                    print(self.rev_lookup_ci)
                else:
                    print(self.rev_lookup)

            if current_value in self.rev_lookup:
                # quick check for if the value has ever been seen before, if not, write required
                match_sets.append(set(self.rev_lookup[current_value]))
            elif self.case_insensitive and current_value.casefold() in self.rev_lookup_ci:
                match_sets.append(set(self.rev_lookup_ci[current_value.casefold()]))
            else:
                if self.debug:
                    print("no matches for rev lookup")
                # return True

        if not match_sets:
            return True

        if cqid:
            matching_qids = {cqid}
        else:
            matching_qids = match_sets[0].intersection(*match_sets[1:])

        # check if there are any items that have all of these values
        # if not, a write is required no matter what
        if not len(matching_qids) == 1:
            if self.debug:
                print(f"no matches ({len(matching_qids)})")
            return True

        qid = matching_qids.pop()
        self.current_qid = qid
        return False

    def write_required(self, data: List[Claim], action_if_exists: ActionIfExists = ActionIfExists.REPLACE, cqid: str = None) -> bool:
        del_props = set()
        data_props = set()
        append_props = []
        if action_if_exists == ActionIfExists.APPEND:
            append_props = [x.mainsnak.property_number for x in data]

        for x in data:
            if x.mainsnak.datavalue and x.mainsnak.datatype:
                data_props.add(x.mainsnak.property_number)
        write_required = False
        self.load_item(data, cqid)

        reconstructed_statements = self.reconstruct_statements(self.current_qid)
        tmp_rs = copy.deepcopy(reconstructed_statements)

        # handle append properties
        for p in append_props:
            app_data = [x for x in data if x.mainsnak.property_number == p]  # new statements
            rec_app_data = [x for x in tmp_rs if x.mainsnak.property_number == p]  # orig statements
            comp = []
            for x in app_data:
                for y in rec_app_data:
                    if x.mainsnak.datavalue == y.mainsnak.datavalue:
                        if y.equals(x, include_ref=self.use_refs) and action_if_exists != ActionIfExists.FORCE_APPEND:
                            comp.append(True)

            # comp = [True for x in app_data for y in rec_app_data if x.equals(y, include_ref=self.use_refs)]
            if len(comp) != len(app_data):
                if self.debug:
                    print(f"failed append: {p}")
                return True

        tmp_rs = [x for x in tmp_rs if x.mainsnak.property_number not in append_props and x.mainsnak.property_number in data_props]

        for date in data:
            # ensure that statements meant for deletion get handled properly
            reconst_props = {x.mainsnak.property_number for x in tmp_rs}
            if not date.mainsnak.datatype and date.mainsnak.property_number in reconst_props:
                if self.debug:
                    print("returned from delete prop handling")
                return True

            if not date.mainsnak.datavalue or not date.mainsnak.datatype:
                # Ignore the deletion statements which are not in the reconstructed statements.
                continue

            if date.mainsnak.property_number in append_props:
                # TODO: check if value already exist and already have the same value
                continue

            if not date.mainsnak.datavalue and not date.mainsnak.datatype:
                del_props.add(date.mainsnak.property_number)

            # this is where the magic happens
            # date is a new statement, proposed to be written
            # tmp_rs are the reconstructed statements == current state of the item
            bool_vec = []
            for x in tmp_rs:
                if (x.mainsnak.datavalue == date.mainsnak.datavalue or (
                        self.case_insensitive and x.mainsnak.datavalue.casefold() == date.mainsnak.datavalue.casefold())) and x.mainsnak.property_number not in del_props:
                    if x.equals(date, include_ref=self.use_refs):
                        bool_vec.append(True)
                    else:
                        bool_vec.append(False)
                else:
                    bool_vec.append(False)
            """
            bool_vec = [x.equals(date, include_ref=self.use_refs, fref=self.ref_comparison_f) and
            x.mainsnak.property_number not in del_props for x in tmp_rs]
            """

            if self.debug:
                print(f"bool_vec: {bool_vec}")
                print("-----------------------------------")
                for x in tmp_rs:
                    if date == x and x.mainsnak.property_number not in del_props:
                        print(x.mainsnak.property_number, x.mainsnak.datavalue, [z.mainsnak.datavalue for z in x.qualifiers])
                        print(date.mainsnak.property_number, date.mainsnak.datavalue, [z.mainsnak.datavalue for z in date.qualifiers])
                    elif x.mainsnak.property_number == date.mainsnak.property_number:
                        print(x.mainsnak.property_number, x.mainsnak.datavalue, [z.mainsnak.datavalue for z in x.qualifiers])
                        print(date.mainsnak.property_number, date.mainsnak.datavalue, [z.mainsnak.datavalue for z in date.qualifiers])

            if not any(bool_vec):
                if self.debug:
                    print(len(bool_vec))
                    print("fast run failed at", date.mainsnak.property_number)
                write_required = True
            else:
                if self.debug:
                    print("fast run success")
                tmp_rs.pop(bool_vec.index(True))

        if len(tmp_rs) > 0:
            if self.debug:
                print("failed because not zero")
                for x in tmp_rs:
                    print("xxx", x.mainsnak.property_number, x.mainsnak.datavalue, [z.mainsnak.datavalue for z in x.qualifiers])
                print("failed because not zero--END")
            write_required = True
        return write_required

    def init_language_data(self, lang: str, lang_data_type: str) -> None:
        """
        Initialize language data store
        :param lang: language code
        :param lang_data_type: 'label', 'description' or 'aliases'
        :return: None
        """
        if lang not in self.loaded_langs:
            self.loaded_langs[lang] = {}

        if lang_data_type not in self.loaded_langs[lang]:
            result = self._query_lang(lang=lang, lang_data_type=lang_data_type)
            if result is not None:
                data = self._process_lang(result=result)
                self.loaded_langs[lang].update({lang_data_type: data})

    def get_language_data(self, qid: str, lang: str, lang_data_type: str) -> List[str]:
        """
        get language data for specified qid

        :param qid:  Wikibase item id
        :param lang: language code
        :param lang_data_type: 'label', 'description' or 'aliases'
        :return: list of strings
        If nothing is found:
            If lang_data_type == label: returns ['']
            If lang_data_type == description: returns ['']
            If lang_data_type == aliases: returns []
        """
        self.init_language_data(lang, lang_data_type)

        current_lang_data = self.loaded_langs[lang][lang_data_type]
        all_lang_strings = current_lang_data.get(qid, [])
        if not all_lang_strings and lang_data_type in {'label', 'description'}:
            all_lang_strings = ['']
        return all_lang_strings

    def check_language_data(self, qid: str, lang_data: List, lang: str, lang_data_type: str, action_if_exists: ActionIfExists = ActionIfExists.APPEND) -> bool:
        """
        Method to check if certain language data exists as a label, description or aliases
        :param qid: Wikibase item id
        :param lang_data: list of string values to check
        :param lang: language code
        :param lang_data_type: What kind of data is it? 'label', 'description' or 'aliases'?
        :param action_if_exists: If aliases already exist, APPEND or REPLACE
        :return: boolean
        """
        all_lang_strings = {x.strip().casefold() for x in self.get_language_data(qid, lang, lang_data_type)}

        if action_if_exists == ActionIfExists.REPLACE:
            return not collections.Counter(all_lang_strings) == collections.Counter(map(lambda x: x.casefold(), lang_data))

        for s in lang_data:
            if s.strip().casefold() not in all_lang_strings:
                if self.debug:
                    print(f"fastrun failed at: {lang_data_type}, string: {s}")
                return True

        return False

    def get_all_data(self) -> Dict[str, dict]:
        return self.prop_data

    def format_query_results(self, r: List, prop_nr: str) -> None:
        """
        `r` is the results of the sparql query in _query_data and is modified in place
        `prop_nr` is needed to get the property datatype to determine how to format the value

        `r` is a list of dicts. The keys are:
            sid: statement ID
            item: the subject. the item this statement is on
            v: the object. The value for this statement
            unit: property unit
            pq: qualifier property
            qval: qualifier value
            qunit: qualifier unit
            ref: reference ID
            pr: reference property
            rval: reference value
        """
        prop_dt = self.get_prop_datatype(prop_nr)
        for i in r:
            for value in {'item', 'sid', 'pq', 'pr', 'ref', 'unit', 'qunit'}:
                if value in i:
                    if i[value]['value'].startswith(self.wikibase_url):
                        i[value] = i[value]['value'].split('/')[-1]
                    else:
                        # TODO: Dirty fix. If we are not on wikidata, we force unitless (Q199) to '1'
                        if i[value]['value'] == 'http://www.wikidata.org/entity/Q199':
                            i[value] = '1'
                        else:
                            i[value] = i[value]['value']

            # make sure datetimes are formatted correctly.
            # the correct format is '+%Y-%m-%dT%H:%M:%SZ', but is sometimes missing the plus??
            # some difference between RDF and xsd:dateTime that I don't understand
            for value in {'v', 'qval', 'rval'}:
                if value in i:
                    if i[value].get("datatype") == 'http://www.w3.org/2001/XMLSchema#dateTime' and not i[value]['value'][0] in '+-':
                        # if it is a dateTime and doesn't start with plus or minus, add a plus
                        i[value]['value'] = '+' + i[value]['value']

            # these three ({'v', 'qval', 'rval'}) are values that can be any data type
            # strip off the URI if they are wikibase-items
            if 'v' in i:
                if i['v']['type'] == 'uri' and prop_dt == 'wikibase-item':
                    i['v'] = i['v']['value'].split('/')[-1]
                elif i['v']['type'] == 'literal' and prop_dt == 'quantity':
                    i['v'] = format_amount(i['v']['value'])
                else:
                    i['v'] = i['v']['value']

                # Note: no-value and some-value don't actually show up in the results here
                # see for example: select * where { wd:Q7207 p:P40 ?c . ?c ?d ?e }
                if type(i['v']) is not dict:
                    self.rev_lookup[i['v']].add(i['item'])
                    if self.case_insensitive:
                        self.rev_lookup_ci[i['v'].casefold()].add(i['item'])

            # handle qualifier value
            if 'qval' in i:
                qual_prop_dt = self.get_prop_datatype(prop_nr=i['pq'])
                if i['qval']['type'] == 'uri' and qual_prop_dt == 'wikibase-item':
                    i['qval'] = i['qval']['value'].split('/')[-1]
                elif i['qval']['type'] == 'literal' and qual_prop_dt == 'quantity':
                    i['qval'] = format_amount(i['qval']['value'])
                else:
                    i['qval'] = i['qval']['value']

            # handle reference value
            if 'rval' in i:
                ref_prop_dt = self.get_prop_datatype(prop_nr=i['pr'])
                if i['rval']['type'] == 'uri' and ref_prop_dt == 'wikibase-item':
                    i['rval'] = i['rval']['value'].split('/')[-1]
                elif i['rval']['type'] == 'literal' and ref_prop_dt == 'quantity':
                    i['rval'] = format_amount(i['rval']['value'])
                else:
                    i['rval'] = i['rval']['value']

    def update_frc_from_query(self, r: List, prop_nr: str) -> None:
        # r is the output of format_query_results
        # this updates the frc from the query (result of _query_data)
        for i in r:
            qid = i['item']
            if qid not in self.prop_data:
                self.prop_data[qid] = {prop_nr: {}}
            if prop_nr not in self.prop_data[qid]:
                self.prop_data[qid].update({prop_nr: {}})
            if i['sid'] not in self.prop_data[qid][prop_nr]:
                self.prop_data[qid][prop_nr].update({i['sid']: {}})
            # update values for this statement (not including ref)
            d = {'v': i['v']}
            self.prop_data[qid][prop_nr][i['sid']].update(d)

            if 'qual' not in self.prop_data[qid][prop_nr][i['sid']]:
                self.prop_data[qid][prop_nr][i['sid']]['qual'] = set()
            if 'pq' in i and 'qval' in i:
                if 'qunit' in i:
                    self.prop_data[qid][prop_nr][i['sid']]['qual'].add((i['pq'], i['qval'], i['qunit']))
                else:
                    self.prop_data[qid][prop_nr][i['sid']]['qual'].add((i['pq'], i['qval'], '1'))

            if 'ref' not in self.prop_data[qid][prop_nr][i['sid']]:
                self.prop_data[qid][prop_nr][i['sid']]['ref'] = {}
            if 'ref' in i:
                if i['ref'] not in self.prop_data[qid][prop_nr][i['sid']]['ref']:
                    self.prop_data[qid][prop_nr][i['sid']]['ref'][i['ref']] = set()
                self.prop_data[qid][prop_nr][i['sid']]['ref'][i['ref']].add((i['pr'], i['rval']))

            if 'unit' not in self.prop_data[qid][prop_nr][i['sid']]:
                self.prop_data[qid][prop_nr][i['sid']]['unit'] = '1'
            if 'unit' in i:
                self.prop_data[qid][prop_nr][i['sid']]['unit'] = i['unit']

    def _query_data(self, prop_nr: str, use_units=False) -> None:
        page_size = 10000
        page_count = 0
        num_pages = None
        if self.debug:
            # get the number of pages/queries so we can show a progress bar
            query = """
            SELECT (COUNT(?item) as ?c) where {{
                  {base_filter}
                  ?item <{wb_url}/prop/{prop_nr}> ?sid .
            }}""".format(wb_url=self.wikibase_url, base_filter=self.base_filter_string, prop_nr=prop_nr)

            if self.debug:
                print(query)

            r = execute_sparql_query(query, endpoint=self.sparql_endpoint_url, debug=self.debug)['results']['bindings']
            count = int(r[0]['c']['value'])
            print(f"Count: {count}")
            num_pages = (int(count) // page_size) + 1
            print(f"Query {prop_nr}: {page_count}/{num_pages}")
        while True:
            # Query header
            query = '''
            #Tool: WikibaseIntegrator wbi_fastrun._query_data
            SELECT ?sid ?item ?v ?unit ?pq ?qval ?qunit ?ref ?pr ?rval
            WHERE
            {{
            '''

            # Base filter
            query += '''
            {base_filter}
            
            ?item <{wb_url}/prop/{prop_nr}> ?sid .
            '''

            # Amount and unit
            if use_units:
                query += '''
                {{
                  <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type .
                  FILTER (?property_type != wikibase:Quantity)
                  ?sid <{wb_url}/prop/statement/{prop_nr}> ?v .
                }}
                # Get amount and unit for the statement
                UNION
                {{
                  ?sid <{wb_url}/prop/statement/value/{prop_nr}> [wikibase:quantityAmount ?v; wikibase:quantityUnit ?unit] .
                }}
                '''
            else:
                query += '''
                <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type .
                ?sid <{wb_url}/prop/statement/{prop_nr}> ?v .
                '''

            # Qualifiers
            # Amount and unit
            if use_units:
                query += '''
                # Get qualifiers
                OPTIONAL
                {{
                  {{
                    # Get simple values for qualifiers which are not of type quantity
                    ?sid ?propQualifier ?qval .
                    ?pq wikibase:qualifier ?propQualifier .
                    ?pq wikibase:propertyType ?qualifer_property_type .
                    FILTER (?qualifer_property_type != wikibase:Quantity)
                  }}
                  UNION
                  {{
                    # Get amount and unit for qualifiers of type quantity
                    ?sid ?pqv [wikibase:quantityAmount ?qval; wikibase:quantityUnit ?qunit] .
                    ?pq wikibase:qualifierValue ?pqv .
                  }}
                }}
                '''
            else:
                query += '''
                # Get qualifiers
                OPTIONAL
                {{
                  # Get simple values for qualifiers
                  ?sid ?propQualifier ?qval .
                  ?pq wikibase:qualifier ?propQualifier .
                  ?pq wikibase:propertyType ?qualifer_property_type .
                }}
                '''

            # References
            if self.use_refs:
                query += '''
                # get references
                OPTIONAL {{
                  ?sid prov:wasDerivedFrom ?ref .
                  ?ref ?pr ?rval .
                  [] wikibase:reference ?pr
                }}
                '''
            # Query footer
            query += '''
            }} ORDER BY ?sid OFFSET {offset} LIMIT {page_size}
            '''

            # Format the query
            query = query.format(wb_url=self.wikibase_url, base_filter=self.base_filter_string, prop_nr=prop_nr, offset=str(page_count * page_size), page_size=str(page_size))

            if self.debug:
                print(query)

            results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']
            self.format_query_results(results, prop_nr)
            self.update_frc_from_query(results, prop_nr)
            page_count += 1
            if num_pages:
                print(f"Query {prop_nr}: {page_count}/{num_pages}")
            if len(results) == 0 or len(results) < page_size:
                break

    def _query_lang(self, lang: str, lang_data_type: str) -> Optional[List[Dict[str, dict]]]:
        """

        :param lang:
        :param lang_data_type:
        """

        lang_data_type_dict = {
            'label': 'rdfs:label',
            'description': 'schema:description',
            'aliases': 'skos:altLabel'
        }

        query = '''
        #Tool: WikibaseIntegrator wbi_fastrun._query_lang
        SELECT ?item ?label WHERE {{
            {base_filter}

            OPTIONAL {{
                ?item {lang_data_type} ?label FILTER (lang(?label) = "{lang}") .
            }}
        }}
        '''.format(base_filter=self.base_filter_string, lang_data_type=lang_data_type_dict[lang_data_type], lang=lang)

        if self.debug:
            print(query)

        return execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

    @staticmethod
    def _process_lang(result: List) -> defaultdict[str, set]:
        data = defaultdict(set)
        for r in result:
            qid = r['item']['value'].split("/")[-1]
            if 'label' in r:
                data[qid].add(r['label']['value'])
        return data

    @lru_cache(maxsize=100000)
    def get_prop_datatype(self, prop_nr: str) -> Optional[str]:
        from wikibaseintegrator import WikibaseIntegrator
        wbi = WikibaseIntegrator()
        property = wbi.property.get(prop_nr)
        return property.datatype

    def clear(self) -> None:
        """
        convinience function to empty this fastrun container
        """
        self.prop_dt_map = {}
        self.prop_data = {}
        self.rev_lookup = defaultdict(set)
        self.rev_lookup_ci = defaultdict(set)

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


def freezeargs(func):
    """Transform mutable dictionnary
    Into immutable
    Useful to be compatible with cache
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        args = tuple(frozendict(arg) if isinstance(arg, dict) else arg for arg in args)
        kwargs = {k: frozendict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        return func(*args, **kwargs)

    return wrapped


def get_fastrun_container(base_filter=None, use_refs=False, case_insensitive=False) -> FastRunContainer:
    if base_filter is None:
        base_filter = {}

    fastrun_container = search_fastrun_store(base_filter=base_filter, use_refs=use_refs, case_insensitive=case_insensitive)
    fastrun_container.current_qid = ''
    fastrun_container.base_data_type = BaseDataType

    return fastrun_container


@freezeargs
@lru_cache()
def search_fastrun_store(base_filter=None, use_refs=False, case_insensitive=False) -> FastRunContainer:
    for c in fastrun_store:
        if (c.base_filter == base_filter) and (c.use_refs == use_refs) and (c.case_insensitive == case_insensitive) and (
                c.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
            return c

    # In case nothing was found in the fastrun_store
    if config['DEBUG']:
        print("Create a new FastRunContainer")
    fastrun_container = FastRunContainer(base_filter=base_filter, use_refs=use_refs, base_data_type=BaseDataType, case_insensitive=case_insensitive)
    fastrun_store.append(fastrun_container)
    return fastrun_container
