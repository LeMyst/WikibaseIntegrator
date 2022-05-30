from __future__ import annotations

import collections
import copy
import logging
from collections import defaultdict
from functools import lru_cache
from itertools import chain
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Type, Union

from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models import Claim
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_helpers import execute_sparql_query, format_amount

if TYPE_CHECKING:
    from wikibaseintegrator.models import Claims

log = logging.getLogger(__name__)

fastrun_store: List[FastRunContainer] = []


class FastRunContainer:
    def __init__(self, base_data_type: Type[BaseDataType], mediawiki_api_url: str = None, sparql_endpoint_url: str = None, wikibase_url: str = None,
                 base_filter: List[BaseDataType | List[BaseDataType]] = None, use_refs: bool = False, case_insensitive: bool = False):
        self.reconstructed_statements: List[BaseDataType] = []
        self.rev_lookup: defaultdict[str, Set[str]] = defaultdict(set)
        self.rev_lookup_ci: defaultdict[str, Set[str]] = defaultdict(set)
        self.prop_data: Dict[str, Dict] = {}
        self.loaded_langs: Dict[str, Dict] = {}
        self.base_filter: List[BaseDataType | List[BaseDataType]] = []
        self.base_filter_string = ''
        self.prop_dt_map: Dict[str, str] = {}

        self.base_data_type: Type[BaseDataType] = base_data_type
        self.mediawiki_api_url: str = str(mediawiki_api_url or config['MEDIAWIKI_API_URL'])
        self.sparql_endpoint_url: str = str(sparql_endpoint_url or config['SPARQL_ENDPOINT_URL'])
        self.wikibase_url: str = str(wikibase_url or config['WIKIBASE_URL'])
        self.use_refs: bool = use_refs
        self.case_insensitive: bool = case_insensitive

        if base_filter and any(base_filter):
            self.base_filter = base_filter
            for k in self.base_filter:
                if isinstance(k, BaseDataType):
                    if k.mainsnak.datavalue:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> {entity} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr=k.mainsnak.property_number, entity=k.get_sparql_value().format(wb_url=self.wikibase_url))
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> ?zz{prop_nr} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr=k.mainsnak.property_number)
                elif isinstance(k, list) and len(k) == 2 and isinstance(k[0], BaseDataType) and isinstance(k[1], BaseDataType):
                    if k[0].mainsnak.datavalue:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}>/<{wb_url}/prop/direct/{prop_nr2}>* {entity} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr=k[0].mainsnak.property_number, prop_nr2=k[1].mainsnak.property_number,
                            entity=k[0].get_sparql_value().format(wb_url=self.wikibase_url))
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* ?zz{prop_nr1}{prop_nr2} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr1=k[0].mainsnak.property_number, prop_nr2=k[1].mainsnak.property_number)
                else:
                    raise ValueError("base_filter must be an instance of BaseDataType or a list of instances of BaseDataType")

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
            for _, d in dt.items():
                qualifiers = []
                for q in d['qual']:
                    f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[q[0]]][0]
                    # TODO: Add support for more data type (Time, MonolingualText, GlobeCoordinate)
                    if self.prop_dt_map[q[0]] == 'quantity':
                        qualifiers.append(f(value=q[1], prop_nr=q[0], unit=q[2]))
                    else:
                        qualifiers.append(f(value=q[1], prop_nr=q[0]))

                references = []
                for _, refs in d['ref'].items():
                    this_ref = []
                    for ref in refs:
                        f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[ref[0]]][0]
                        this_ref.append(f(value=ref[1], prop_nr=ref[0]))
                    references.append(this_ref)

                f = [x for x in self.base_data_type.subclasses if x.DTYPE == self.prop_dt_map[prop_nr]][0]
                # TODO: Add support for more data type
                if self.prop_dt_map[prop_nr] == 'quantity':
                    datatype = f(prop_nr=prop_nr, qualifiers=qualifiers, references=references, unit=d['unit'])
                    datatype.parse_sparql_value(value=d['v'], unit=d['unit'])
                else:
                    datatype = f(prop_nr=prop_nr, qualifiers=qualifiers, references=references)
                    datatype.parse_sparql_value(value=d['v'])
                reconstructed_statements.append(datatype)

        # this isn't used. done for debugging purposes
        self.reconstructed_statements = reconstructed_statements
        return reconstructed_statements

    def get_items(self, claims: Union[List[Claim], Claims, Claim], cqid: str = None) -> Optional[Set[str]]:
        """
        Get items ID from a SPARQL endpoint

        :param claims: A list of claims the entities should have
        :param cqid:
        :return: a list of entity ID or None
        :exception: if there is more than one claim
        """
        match_sets = []

        if isinstance(claims, Claim):
            claims = [claims]
        elif (not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims):
            raise ValueError("claims must be an instance of Claim or Claims or a list of Claim")

        for claim in claims:
            # skip to next if statement has no value or no data type defined, e.g. for deletion objects
            if not claim.mainsnak.datavalue and not claim.mainsnak.datatype:
                continue

            prop_nr = claim.mainsnak.property_number

            if prop_nr not in self.prop_dt_map:
                log.debug("%s not found in fastrun", prop_nr)

                if isinstance(claim, BaseDataType) and type(claim) != BaseDataType:  # pylint: disable=unidiomatic-typecheck
                    self.prop_dt_map.update({prop_nr: claim.DTYPE})
                else:
                    self.prop_dt_map.update({prop_nr: self.get_prop_datatype(prop_nr)})
                self._query_data(prop_nr=prop_nr, use_units=self.prop_dt_map[prop_nr] == 'quantity')

            # noinspection PyProtectedMember
            current_value = claim.get_sparql_value()

            if self.prop_dt_map[prop_nr] == 'wikibase-item':
                current_value = claim.mainsnak.datavalue['value']['id']

            log.debug(current_value)
            # if self.case_insensitive:
            #     log.debug("case insensitive enabled")
            #     log.debug(self.rev_lookup_ci)
            # else:
            #     log.debug(self.rev_lookup)

            if current_value in self.rev_lookup:
                # quick check for if the value has ever been seen before, if not, write required
                match_sets.append(set(self.rev_lookup[current_value]))
            elif self.case_insensitive and current_value.casefold() in self.rev_lookup_ci:
                match_sets.append(set(self.rev_lookup_ci[current_value.casefold()]))
            else:
                log.debug("no matches for rev lookup for %s", current_value)

        if not match_sets:
            return None

        if cqid:
            matching_qids = {cqid}
        else:
            matching_qids = match_sets[0].intersection(*match_sets[1:])

        return matching_qids

    def get_item(self, claims: Union[List[Claim], Claims, Claim], cqid: str = None) -> Optional[str]:
        """

        :param claims: A list of claims the entity should have
        :param cqid:
        :return: An entity ID, None if there is more than one.
        """

        matching_qids: Optional[Set[str]] = self.get_items(claims=claims, cqid=cqid)

        if matching_qids is None:
            return None

        # check if there are any items that have all of these values
        # if not, a write is required no matter what
        if not len(matching_qids) == 1:
            log.debug("no matches (%s)", len(matching_qids))
            return None

        return matching_qids.pop()

    def write_required(self, data: List[Claim], action_if_exists: ActionIfExists = ActionIfExists.REPLACE, cqid: str = None) -> bool:
        """
        Check if a write is required

        :param data:
        :param action_if_exists:
        :param cqid:
        :return: Return True if the write is required
        """
        del_props = set()
        data_props = set()
        append_props = []
        if action_if_exists == ActionIfExists.APPEND:
            append_props = [x.mainsnak.property_number for x in data]

        for x in data:
            if x.mainsnak.datavalue and x.mainsnak.datatype:
                data_props.add(x.mainsnak.property_number)
        qid = self.get_item(data, cqid)

        if not qid:
            return True

        reconstructed_statements = self.reconstruct_statements(qid)
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
                log.debug("failed append: %s", p)
                return True

        tmp_rs = [x for x in tmp_rs if x.mainsnak.property_number not in append_props and x.mainsnak.property_number in data_props]

        for date in data:
            # ensure that statements meant for deletion get handled properly
            reconst_props = {x.mainsnak.property_number for x in tmp_rs}
            if not date.mainsnak.datatype and date.mainsnak.property_number in reconst_props:
                log.debug("returned from delete prop handling")
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
                if (x == date or (self.case_insensitive and x.mainsnak.datavalue.casefold() == date.mainsnak.datavalue.casefold())) and x.mainsnak.property_number not in del_props:
                    bool_vec.append(x.equals(date, include_ref=self.use_refs))
                else:
                    bool_vec.append(False)
            # bool_vec = [x.equals(date, include_ref=self.use_refs, fref=self.ref_comparison_f) and
            # x.mainsnak.property_number not in del_props for x in tmp_rs]

            log.debug("bool_vec: %s", bool_vec)
            log.debug("-----------------------------------")
            for x in tmp_rs:
                if x == date and x.mainsnak.property_number not in del_props:
                    log.debug([x.mainsnak.property_number, x.mainsnak.datavalue, [z.datavalue for z in x.qualifiers]])
                    log.debug([date.mainsnak.property_number, date.mainsnak.datavalue, [z.datavalue for z in date.qualifiers]])
                elif x.mainsnak.property_number == date.mainsnak.property_number:
                    log.debug([x.mainsnak.property_number, x.mainsnak.datavalue, [z.datavalue for z in x.qualifiers]])
                    log.debug([date.mainsnak.property_number, date.mainsnak.datavalue, [z.datavalue for z in date.qualifiers]])

            if not any(bool_vec):
                log.debug(len(bool_vec))
                log.debug("fast run failed at %s", date.mainsnak.property_number)
                return True

            log.debug("fast run success")
            tmp_rs.pop(bool_vec.index(True))

        if len(tmp_rs) > 0:
            log.debug("failed because not zero")
            for x in tmp_rs:
                log.debug([x.mainsnak.property_number, x.mainsnak.datavalue, [z.mainsnak.datavalue for z in x.qualifiers]])
            log.debug("failed because not zero--END")
            return True

        return False

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
            return collections.Counter(all_lang_strings) != collections.Counter(map(lambda x: x.casefold(), lang_data))

        for s in lang_data:
            if s.strip().casefold() not in all_lang_strings:
                log.debug("fastrun failed at: %s, string: %s", lang_data_type, s)
                return True

        return False

    def get_all_data(self) -> Dict[str, Dict]:
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
            for value in ['item', 'sid', 'pq', 'pr', 'ref', 'unit', 'qunit']:
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
            for value in ['v', 'qval', 'rval']:
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
                elif i['v']['type'] == 'literal' and prop_dt == 'monolingualtext':
                    f = [x for x in self.base_data_type.subclasses if x.DTYPE == prop_dt][0](prop_nr=prop_nr, text=i['v']['value'], language=i['v']['xml:lang'])
                    i['v'] = f.get_sparql_value()
                else:
                    f = [x for x in self.base_data_type.subclasses if x.DTYPE == prop_dt][0](prop_nr=prop_nr)
                    if not f.parse_sparql_value(value=i['v']['value'], type=i['v']['type']):
                        raise ValueError("Can't parse the value with parse_sparql_value()")
                    i['v'] = f.get_sparql_value()

                # Note: no-value and some-value don't actually show up in the results here
                # see for example: select * where { wd:Q7207 p:P40 ?c . ?c ?d ?e }
                if not isinstance(i['v'], dict):
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

    def _query_data(self, prop_nr: str, use_units: bool = False, page_size: int = 10000) -> None:
        page_count = 0

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

            results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']
            self.format_query_results(results, prop_nr)
            self.update_frc_from_query(results, prop_nr)
            page_count += 1

            if len(results) == 0 or len(results) < page_size:
                break

    def _query_lang(self, lang: str, lang_data_type: str) -> Optional[List[Dict[str, Dict]]]:
        """

        :param lang:
        :param lang_data_type:
        """

        lang_data_type_dict = {
            'label': 'rdfs:label',
            'description': 'schema:description',
            'aliases': 'skos:altLabel'
        }

        query = f'''
        #Tool: WikibaseIntegrator wbi_fastrun._query_lang
        SELECT ?item ?label WHERE {{
            {self.base_filter_string}

            OPTIONAL {{
                ?item {lang_data_type_dict[lang_data_type]} ?label FILTER (lang(?label) = "{lang}") .
            }}
        }}
        '''

        log.debug(query)

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
    def get_prop_datatype(self, prop_nr: str) -> Optional[str]:  # pylint: disable=no-self-use
        from wikibaseintegrator import WikibaseIntegrator
        wbi = WikibaseIntegrator()
        property = wbi.property.get(prop_nr)
        return property.datatype

    def clear(self) -> None:
        """
        convenience function to empty this fastrun container
        """
        self.prop_dt_map = {}
        self.prop_data = {}
        self.rev_lookup = defaultdict(set)
        self.rev_lookup_ci = defaultdict(set)

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


def get_fastrun_container(base_filter: List[BaseDataType | List[BaseDataType]] = None, use_refs: bool = False, case_insensitive: bool = False) -> FastRunContainer:
    if base_filter is None:
        base_filter = []

    # We search if we already have a FastRunContainer with the same parameters to re-use it
    fastrun_container = _search_fastrun_store(base_filter=base_filter, use_refs=use_refs, case_insensitive=case_insensitive)

    return fastrun_container


def _search_fastrun_store(base_filter: List[BaseDataType | List[BaseDataType]] = None, use_refs: bool = False, case_insensitive: bool = False) -> FastRunContainer:
    for fastrun in fastrun_store:
        if (fastrun.base_filter == base_filter) and (fastrun.use_refs == use_refs) and (fastrun.case_insensitive == case_insensitive) and (
                fastrun.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
            return fastrun

    # In case nothing was found in the fastrun_store
    log.info("Create a new FastRunContainer")

    fastrun_container = FastRunContainer(base_data_type=BaseDataType, base_filter=base_filter, use_refs=use_refs, case_insensitive=case_insensitive)
    fastrun_store.append(fastrun_container)
    return fastrun_container
