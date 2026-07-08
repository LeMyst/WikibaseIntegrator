from __future__ import annotations

import collections
import copy
import logging
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING

from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.models import Claim
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseDatatype
from wikibaseintegrator.wbi_helpers import execute_sparql_query, format_amount

if TYPE_CHECKING:
    from wikibaseintegrator.models import Claims

log = logging.getLogger(__name__)

fastrun_store: list[FastRunContainer] = []

# The RDF export of a Wikibase instance always represents a quantity without a unit ('1' in the JSON representation)
# with the Wikidata entity Q199 (the number one), whatever the instance.
UNITLESS_UNIT_URI = 'http://www.wikidata.org/entity/Q199'


class FastRunContainer:
    def __init__(self, base_data_type: type[BaseDataType], mediawiki_api_url: str | None = None, sparql_endpoint_url: str | None = None, wikibase_url: str | None = None,
                 base_filter: list[BaseDataType | list[BaseDataType]] | None = None, use_refs: bool = False, case_insensitive: bool = False):
        self.reconstructed_statements: list[BaseDataType] = []
        self.rev_lookup: defaultdict[str, set[str]] = defaultdict(set)
        self.rev_lookup_ci: defaultdict[str, set[str]] = defaultdict(set)
        self.prop_data: dict[str, dict] = {}
        self.loaded_langs: dict[str, dict] = {}
        self.base_filter: list[BaseDataType | list[BaseDataType]] = []
        self.base_filter_string = ''
        self.prop_dt_map: dict[str, str | None] = {}

        self.base_data_type: type[BaseDataType] = base_data_type
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

    def _get_datatype_class(self, datatype: str | None) -> type[BaseDataType]:
        """
        Return the data type class implementing the given Wikibase datatype (e.g. 'external-id' -> ExternalID).

        :param datatype: A Wikibase datatype name
        :exception ValueError: if no class implements the given datatype
        """
        for subclass in self.base_data_type.subclasses:
            if subclass.DTYPE == datatype:
                return subclass
        raise ValueError(f"No data type class found for datatype '{datatype}'")

    def _reconstruct_snak_datatype(self, prop_nr: str, value: str, unit: str = '1') -> BaseDataType:
        """
        Rebuild a datatype object from the raw SPARQL value stored in prop_data, used for qualifiers and references.

        :param prop_nr: The property number of the snak
        :param value: The raw SPARQL value
        :param unit: The unit entity ID if the value is a quantity
        :exception ValueError: if the value can't be parsed by the datatype class
        """
        datatype = self._get_datatype_class(self.prop_dt_map[prop_nr])(prop_nr=prop_nr)
        if not datatype.parse_sparql_value(value=value, unit=unit):
            raise ValueError(f"Can't parse the value '{value}' of property {prop_nr} with parse_sparql_value()")
        return datatype

    def reconstruct_statements(self, qid: str) -> list[BaseDataType]:
        reconstructed_statements: list[BaseDataType] = []

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
            # Note: attributes missing from the SPARQL simple values (time precision, globe coordinate precision,
            # quantity bounds...) are rebuilt with their default value, so statements using non-default attributes
            # are always reported as requiring a write.
            for _, d in dt.items():
                qualifiers = [self._reconstruct_snak_datatype(prop_nr=q[0], value=q[1], unit=q[2]) for q in d['qual']]

                references = []
                for _, refs in d['ref'].items():
                    references.append([self._reconstruct_snak_datatype(prop_nr=ref[0], value=ref[1]) for ref in refs])

                f = self._get_datatype_class(self.prop_dt_map[prop_nr])
                datatype = f(prop_nr=prop_nr, qualifiers=qualifiers, references=references)
                if not datatype.parse_sparql_value(value=d['v'], unit=d.get('unit', '1')):
                    raise ValueError(f"Can't parse the value '{d['v']}' of property {prop_nr} with parse_sparql_value()")
                reconstructed_statements.append(datatype)

        # this isn't used. done for debugging purposes
        self.reconstructed_statements = reconstructed_statements
        return reconstructed_statements

    def get_items(self, claims: list[Claim] | Claims | Claim, cqid: str | None = None) -> set[str] | None:
        """
        Get items ID from a SPARQL endpoint

        :param claims: A list of claims the entities should have
        :param cqid: If given, this entity ID is returned instead of the IDs found by the value lookup
        :return: a set of entity IDs or None if no entity matches the claims
        """
        match_sets = []

        if isinstance(claims, Claim):
            claims = [claims]
        elif (not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims):
            raise ValueError("claims must be an instance of Claim or Claims or a list of Claim")

        for claim in claims:
            # skip to next if statement has no value or no data type defined, e.g. for deletion objects
            if not claim.mainsnak.datavalue or not claim.mainsnak.datatype:
                continue

            prop_nr = claim.mainsnak.property_number

            if prop_nr not in self.prop_dt_map:
                log.debug("%s not found in fastrun", prop_nr)

                if isinstance(claim, BaseDataType) and type(claim) != BaseDataType:  # pylint: disable=unidiomatic-typecheck
                    self.prop_dt_map.update({prop_nr: claim.DTYPE})
                else:
                    self.prop_dt_map.update({prop_nr: self.get_prop_datatype(prop_nr)})
                self._query_data(prop_nr=prop_nr, use_units=self.prop_dt_map[prop_nr] == 'quantity')

            # The value must be formatted the same way as the rev_lookup keys built in format_query_results()
            if self.prop_dt_map[prop_nr] == 'wikibase-item':
                current_value = claim.mainsnak.datavalue['value']['id']
            elif self.prop_dt_map[prop_nr] == 'quantity':
                # rev_lookup stores plain amounts (e.g. '+42'), not the full SPARQL literal returned by get_sparql_value()
                current_value = format_amount(claim.mainsnak.datavalue['value']['amount'])
            else:
                current_value = claim.get_sparql_value()

            log.debug(current_value)

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

    def get_item(self, claims: list[Claim] | Claims | Claim, cqid: str | None = None) -> str | None:
        """

        :param claims: A list of claims the entity should have
        :param cqid:
        :return: An entity ID, None if there is more than one.
        """

        matching_qids: set[str] | None = self.get_items(claims=claims, cqid=cqid)

        if matching_qids is None:
            return None

        # check if there are any items that have all of these values
        # if not, a write is required no matter what
        if not len(matching_qids) == 1:
            log.debug("no matches (%s)", len(matching_qids))
            return None

        return matching_qids.pop()

    def write_required(self, data: list[Claim], action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL, cqid: str | None = None) -> bool:
        """
        Check if a write is required

        :param data:
        :param action_if_exists:
        :param cqid:
        :return: Return True if the write is required
        """
        data_props = set()
        append_props: list[str] = []
        if action_if_exists in (ActionIfExists.APPEND_OR_REPLACE, ActionIfExists.FORCE_APPEND):
            append_props = [x.mainsnak.property_number for x in data]

        if append_props and action_if_exists == ActionIfExists.FORCE_APPEND:
            # The new statements are always appended, so a write is always required
            log.debug("force append: write required")
            return True

        for x in data:
            if x.mainsnak.datavalue and x.mainsnak.datatype:
                data_props.add(x.mainsnak.property_number)
        qid = self.get_item(data, cqid)

        if not qid:
            return True

        reconstructed_statements = self.reconstruct_statements(qid)
        tmp_rs = copy.deepcopy(reconstructed_statements)

        # handle append properties: every new statement must already exist on the item with the same value
        # (and the same references if use_refs is enabled), otherwise a write is required
        for p in set(append_props):
            app_data = [x for x in data if x.mainsnak.property_number == p]  # new statements
            rec_app_data = [x for x in tmp_rs if x.mainsnak.property_number == p]  # orig statements
            for new_statement in app_data:
                if not any(original.mainsnak.datavalue == new_statement.mainsnak.datavalue and original.equals(new_statement, include_ref=self.use_refs)
                           for original in rec_app_data):
                    log.debug("failed append: %s", p)
                    return True

        tmp_rs = [x for x in tmp_rs if x.mainsnak.property_number not in append_props and x.mainsnak.property_number in data_props]

        for statement in data:
            # ensure that statements meant for deletion get handled properly
            reconst_props = {x.mainsnak.property_number for x in tmp_rs}
            if not statement.mainsnak.datatype and statement.mainsnak.property_number in reconst_props:
                log.debug("returned from delete prop handling")
                return True

            if not statement.mainsnak.datavalue or not statement.mainsnak.datatype:
                # Ignore the deletion statements which are not in the reconstructed statements.
                continue

            if statement.mainsnak.property_number in append_props:
                continue

            # this is where the magic happens
            # statement is a new statement, proposed to be written
            # tmp_rs are the reconstructed statements == current state of the item
            bool_vec = [self._statements_equal(x, statement) for x in tmp_rs]

            if log.isEnabledFor(logging.DEBUG):
                log.debug("bool_vec: %s", bool_vec)
                log.debug("-----------------------------------")
                for x in tmp_rs:
                    if x.mainsnak.property_number == statement.mainsnak.property_number:
                        log.debug([x.mainsnak.property_number, x.mainsnak.datavalue, [z.datavalue for z in x.qualifiers]])
                        log.debug([statement.mainsnak.property_number, statement.mainsnak.datavalue, [z.datavalue for z in statement.qualifiers]])

            if not any(bool_vec):
                log.debug("fast run failed at %s (%s candidate statements)", statement.mainsnak.property_number, len(bool_vec))
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

    def _statements_equal(self, statement: BaseDataType, new_statement: Claim) -> bool:
        """
        Compare a reconstructed statement with a new statement, including the references if use_refs is enabled.
        When case_insensitive is enabled, string values differing only by case are considered equal.

        :param statement: A statement reconstructed from the SPARQL data (the current state of the entity)
        :param new_statement: The statement proposed to be written
        :return: True if both statements are considered equal
        """
        if statement.equals(new_statement, include_ref=self.use_refs):
            return True

        if not self.case_insensitive or statement.mainsnak.property_number != new_statement.mainsnak.property_number:
            return False

        current_value = (statement.mainsnak.datavalue or {}).get('value')
        new_value = (new_statement.mainsnak.datavalue or {}).get('value')
        if not isinstance(current_value, str) or not isinstance(new_value, str) or current_value.casefold() != new_value.casefold():
            return False

        if not statement.has_equal_qualifiers(new_statement):
            return False

        return not self.use_refs or Claim.refs_equal(statement, new_statement)

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

    def get_language_data(self, qid: str, lang: str, lang_data_type: str) -> list[str]:
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

    def check_language_data(self, qid: str, lang_data: list, lang: str, lang_data_type: str, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> bool:
        """
        Method to check if certain language data exists as a label, description or aliases
        :param qid: Wikibase item id
        :param lang_data: list of string values to check
        :param lang: language code
        :param lang_data_type: What kind of data is it? 'label', 'description' or 'aliases'?
        :param action_if_exists: If aliases already exist, APPEND_OR_REPLACE or REPLACE_ALL
        :return: boolean
        """
        all_lang_strings = {x.strip().casefold() for x in self.get_language_data(qid, lang, lang_data_type)}

        if action_if_exists == ActionIfExists.REPLACE_ALL:
            return collections.Counter(all_lang_strings) != collections.Counter(map(lambda x: x.casefold(), lang_data))

        for s in lang_data:
            if s.strip().casefold() not in all_lang_strings:
                log.debug("fastrun failed at: %s, string: %s", lang_data_type, s)
                return True

        return False

    def get_all_data(self) -> dict[str, dict]:
        return self.prop_data

    def _normalize_unit(self, unit_uri: str) -> str:
        """
        Normalize a unit URI from the SPARQL results to the format used in the JSON representation: the entity ID for
        the units local to the instance, and '1' for unitless quantities, which the RDF export always represents with
        the Wikidata entity Q199, whatever the Wikibase instance.

        :param unit_uri: The unit URI from the SPARQL results
        """
        if unit_uri == UNITLESS_UNIT_URI:
            return '1'
        if unit_uri.startswith(self.wikibase_url):
            return unit_uri.split('/')[-1]
        return unit_uri

    def format_query_results(self, r: list, prop_nr: str) -> None:
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
            for value in ['item', 'sid', 'pq', 'pr', 'ref']:
                if value in i:
                    if i[value]['value'].startswith(self.wikibase_url):
                        i[value] = i[value]['value'].split('/')[-1]
                    else:
                        i[value] = i[value]['value']

            # normalize the unit URIs to entity IDs and the unitless unit to '1'
            for value in ['unit', 'qunit']:
                if value in i:
                    i[value] = self._normalize_unit(i[value]['value'])

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
                    f = self._get_datatype_class(prop_dt)(prop_nr=prop_nr, text=i['v']['value'], language=i['v']['xml:lang'])
                    i['v'] = f.get_sparql_value()
                else:
                    f = self._get_datatype_class(prop_dt)(prop_nr=prop_nr)
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
                elif i['qval']['type'] == 'literal' and qual_prop_dt == 'monolingualtext' and 'xml:lang' in i['qval']:
                    # keep the language, it is needed to reconstruct the qualifier
                    i['qval'] = self._get_datatype_class(qual_prop_dt)(prop_nr=i['pq'], text=i['qval']['value'], language=i['qval']['xml:lang']).get_sparql_value()
                else:
                    i['qval'] = i['qval']['value']

            # handle reference value
            if 'rval' in i:
                ref_prop_dt = self.get_prop_datatype(prop_nr=i['pr'])
                if i['rval']['type'] == 'uri' and ref_prop_dt == 'wikibase-item':
                    i['rval'] = i['rval']['value'].split('/')[-1]
                elif i['rval']['type'] == 'literal' and ref_prop_dt == 'quantity':
                    i['rval'] = format_amount(i['rval']['value'])
                elif i['rval']['type'] == 'literal' and ref_prop_dt == 'monolingualtext' and 'xml:lang' in i['rval']:
                    # keep the language, it is needed to reconstruct the reference
                    i['rval'] = self._get_datatype_class(ref_prop_dt)(prop_nr=i['pr'], text=i['rval']['value'], language=i['rval']['xml:lang']).get_sparql_value()
                else:
                    i['rval'] = i['rval']['value']

    def update_frc_from_query(self, r: list, prop_nr: str) -> None:
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

            if len(results) < page_size:
                break

    def _query_lang(self, lang: str, lang_data_type: str) -> list[dict[str, dict]] | None:
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
    def _process_lang(result: list) -> defaultdict[str, set]:
        data = defaultdict(set)
        for r in result:
            qid = r['item']['value'].split("/")[-1]
            if 'label' in r:
                data[qid].add(r['label']['value'])
        return data

    def get_prop_datatype(self, prop_nr: str) -> str | None:
        # Memoize in the per-instance prop_dt_map: this is tied to the container's lifetime (no global cache keeping
        # containers alive), avoids re-instantiating WikibaseIntegrator and re-querying the API on cache hits, and is
        # invalidated by clear().
        if prop_nr not in self.prop_dt_map:
            from wikibaseintegrator import WikibaseIntegrator
            wbi = WikibaseIntegrator()
            datatype = wbi.property.get(prop_nr).datatype
            if isinstance(datatype, WikibaseDatatype):
                datatype = datatype.value
            self.prop_dt_map[prop_nr] = datatype
        return self.prop_dt_map[prop_nr]

    def clear(self) -> None:
        """
        convenience function to empty this fastrun container
        """
        self.prop_dt_map = {}
        self.prop_data = {}
        self.rev_lookup = defaultdict(set)
        self.rev_lookup_ci = defaultdict(set)
        self.loaded_langs = {}

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


def get_fastrun_container(base_filter: list[BaseDataType | list[BaseDataType]] | None = None, use_refs: bool = False, case_insensitive: bool = False) -> FastRunContainer:
    if base_filter is None:
        base_filter = []

    # We search if we already have a FastRunContainer with the same parameters to reuse it
    fastrun_container = _search_fastrun_store(base_filter=base_filter, use_refs=use_refs, case_insensitive=case_insensitive)

    return fastrun_container


def _search_fastrun_store(base_filter: list[BaseDataType | list[BaseDataType]] | None = None, use_refs: bool = False, case_insensitive: bool = False) -> FastRunContainer:
    for fastrun in fastrun_store:
        if (fastrun.base_filter == base_filter) and (fastrun.use_refs == use_refs) and (fastrun.case_insensitive == case_insensitive) and (
                fastrun.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
            return fastrun

    # In case nothing was found in the fastrun_store
    log.info("Create a new FastRunContainer")

    fastrun_container = FastRunContainer(base_data_type=BaseDataType, base_filter=base_filter, use_refs=use_refs, case_insensitive=case_insensitive)
    fastrun_store.append(fastrun_container)
    return fastrun_container
