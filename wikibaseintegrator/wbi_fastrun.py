import collections
import copy
from collections import defaultdict
from functools import lru_cache
from itertools import chain

from wikibaseintegrator import wbi_core
from wikibaseintegrator.wbi_config import config


class FastRunContainer(object):
    def __init__(self, base_data_type, engine, mediawiki_api_url=None, sparql_endpoint_url=None, wikibase_url=None,
                 base_filter=None, use_refs=False, ref_handler=None, case_insensitive=False, debug=False):
        self.reconstructed_statements = []
        self.rev_lookup = defaultdict(set)
        self.rev_lookup_ci = defaultdict(set)
        self.prop_data = {}
        self.loaded_langs = {}
        self.statements = []
        self.base_filter = {}
        self.base_filter_string = ''
        self.prop_dt_map = {}
        self.current_qid = ''

        self.base_data_type = base_data_type
        self.engine = engine
        self.mediawiki_api_url = config['MEDIAWIKI_API_URL'] if mediawiki_api_url is None else mediawiki_api_url
        self.sparql_endpoint_url = config['SPARQL_ENDPOINT_URL'] if sparql_endpoint_url is None else sparql_endpoint_url
        self.wikibase_url = config['WIKIBASE_URL'] if wikibase_url is None else wikibase_url
        self.use_refs = use_refs
        self.ref_handler = ref_handler
        self.case_insensitive = case_insensitive
        self.debug = debug

        if base_filter and any(base_filter):
            self.base_filter = base_filter
            for k, v in self.base_filter.items():
                ks = []
                if k.count('/') == 1:
                    ks = k.split('/')
                if v:
                    if ks:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* <{wb_url}/entity/{entity}> .\n'.format(
                            wb_url=self.wikibase_url, prop_nr1=ks[0], prop_nr2=ks[1], entity=v)
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> <{wb_url}/entity/{entity}> .\n'.format(
                            wb_url=self.wikibase_url, prop_nr=k, entity=v)
                else:
                    if ks:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* ?zz{prop_nr1}{prop_nr2} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr1=ks[0], prop_nr2=ks[1])
                    else:
                        self.base_filter_string += '?item <{wb_url}/prop/direct/{prop_nr}> ?zz{prop_nr} .\n'.format(
                            wb_url=self.wikibase_url, prop_nr=k)

    def reconstruct_statements(self, qid: str) -> list:
        reconstructed_statements = []

        if qid not in self.prop_data:
            self.reconstructed_statements = reconstructed_statements
            return reconstructed_statements

        for prop_nr, dt in self.prop_data[qid].items():
            # get datatypes for qualifier props
            q_props = set(chain(*[[x[0] for x in d['qual']] for d in dt.values()]))
            r_props = set(chain(*[set(chain(*[[y[0] for y in x] for x in d['ref'].values()])) for d in dt.values()]))
            props = q_props | r_props
            for prop in props:
                if prop not in self.prop_dt_map:
                    self.prop_dt_map.update({prop: self.get_prop_datatype(prop)})
            # reconstruct statements from frc (including qualifiers, and refs)
            for uid, d in dt.items():
                qualifiers = []
                for q in d['qual']:
                    f = [x for x in self.base_data_type.__subclasses__() if x.DTYPE ==
                         self.prop_dt_map[q[0]]][0]
                    if self.prop_dt_map[q[0]] == 'quantity' and q[2] != '1':
                        qualifiers.append(f(q[1], prop_nr=q[0], is_qualifier=True, unit=q[2]))
                    else:
                        qualifiers.append(f(q[1], prop_nr=q[0], is_qualifier=True))

                references = []
                for ref_id, refs in d['ref'].items():
                    this_ref = []
                    for ref in refs:
                        f = [x for x in self.base_data_type.__subclasses__() if x.DTYPE ==
                             self.prop_dt_map[ref[0]]][0]
                        this_ref.append(f(ref[1], prop_nr=ref[0], is_reference=True))
                    references.append(this_ref)

                f = [x for x in self.base_data_type.__subclasses__() if x.DTYPE ==
                     self.prop_dt_map[prop_nr]][0]
                if self.prop_dt_map[prop_nr] == 'quantity' and d['unit'] != '1':
                    reconstructed_statements.append(
                        f(d['v'], prop_nr=prop_nr, qualifiers=qualifiers, references=references, unit=d['unit']))
                else:
                    reconstructed_statements.append(
                        f(d['v'], prop_nr=prop_nr, qualifiers=qualifiers, references=references))

        # this isn't used. done for debugging purposes
        self.reconstructed_statements = reconstructed_statements
        return reconstructed_statements

    def load_item(self, data: list, cqid=None) -> bool:
        match_sets = []
        for date in data:
            # skip to next if statement has no value or no data type defined, e.g. for deletion objects
            current_value = date.get_value()
            if not current_value and not date.data_type:
                continue

            prop_nr = date.get_prop_nr()

            if prop_nr not in self.prop_dt_map:
                if self.debug:
                    print("{} not found in fastrun".format(prop_nr))
                self.prop_dt_map.update({prop_nr: self.get_prop_datatype(prop_nr)})
                self._query_data(prop_nr)

            # more sophisticated data types like dates and globe coordinates need special treatment here
            if self.prop_dt_map[prop_nr] == 'time':
                current_value = current_value[0]
            elif self.prop_dt_map[prop_nr] == 'wikibase-item':
                if not str(current_value).startswith('Q'):
                    current_value = 'Q{}'.format(current_value)
            elif self.prop_dt_map[prop_nr] == 'quantity':
                current_value = self.format_amount(current_value[0])

            if self.debug:
                print(current_value)

            if current_value in self.rev_lookup:
                # quick check for if the value has ever been seen before, if not, write required
                temp_set = set(self.rev_lookup[current_value])
            elif self.case_insensitive and current_value.casefold() in self.rev_lookup_ci:
                temp_set = set(self.rev_lookup_ci[current_value.casefold()])
            else:
                if self.debug:
                    if self.case_insensitive:
                        print('case insensitive enabled')
                        print(self.rev_lookup_ci)
                    else:
                        print(self.rev_lookup)
                    print('no matches for rev lookup')
                return True
            match_sets.append(temp_set)

        if cqid:
            matching_qids = {cqid}
        else:
            matching_qids = match_sets[0].intersection(*match_sets[1:])

        # check if there are any items that have all of these values
        # if not, a write is required no matter what
        if not len(matching_qids) == 1:
            if self.debug:
                print('no matches ({})'.format(len(matching_qids)))
            return True

        qid = matching_qids.pop()
        self.current_qid = qid

    def write_required(self, data: list, append_props: list = None, cqid=None) -> bool:
        del_props = set()
        data_props = set()
        if not append_props:
            append_props = []

        for x in data:
            if x.value and x.data_type:
                data_props.add(x.get_prop_nr())
        write_required = False
        self.load_item(data, cqid)

        reconstructed_statements = self.reconstruct_statements(self.current_qid)
        tmp_rs = copy.deepcopy(reconstructed_statements)

        # handle append properties
        for p in append_props:
            app_data = [x for x in data if x.get_prop_nr() == p]  # new statements
            rec_app_data = [x for x in tmp_rs if x.get_prop_nr() == p]  # orig statements
            comp = []
            for x in app_data:
                for y in rec_app_data:
                    if x.get_value() == y.get_value():
                        if self.use_refs and self.ref_handler:
                            to_be = copy.deepcopy(y)
                            self.ref_handler(to_be, x)
                        else:
                            to_be = x
                        if y.equals(to_be, include_ref=self.use_refs):
                            comp.append(True)

            # comp = [True for x in app_data for y in rec_app_data if x.equals(y, include_ref=self.use_refs)]
            if len(comp) != len(app_data):
                if self.debug:
                    print("failed append: {}".format(p))
                return True

        tmp_rs = [x for x in tmp_rs if x.get_prop_nr() not in append_props and x.get_prop_nr() in data_props]

        for date in data:
            # ensure that statements meant for deletion get handled properly
            reconst_props = set([x.get_prop_nr() for x in tmp_rs])
            if (not date.value or not date.data_type) and date.get_prop_nr() in reconst_props:
                if self.debug:
                    print('returned from delete prop handling')
                return True
            elif not date.value or not date.data_type:
                # Ignore the deletion statements which are not in the reconstructed statements.
                continue

            if date.get_prop_nr() in append_props:
                continue

            if not date.get_value() and not date.data_type:
                del_props.add(date.get_prop_nr())

            # this is where the magic happens
            # date is a new statement, proposed to be written
            # tmp_rs are the reconstructed statements == current state of the item
            bool_vec = []
            for x in tmp_rs:
                if (x.get_value() == date.get_value() or (
                        self.case_insensitive and x.get_value().casefold() == date.get_value().casefold())) and \
                        x.get_prop_nr() not in del_props:
                    if self.use_refs and self.ref_handler:
                        to_be = copy.deepcopy(x)
                        self.ref_handler(to_be, date)
                    else:
                        to_be = date
                    if x.equals(to_be, include_ref=self.use_refs):
                        bool_vec.append(True)
                    else:
                        bool_vec.append(False)
                else:
                    bool_vec.append(False)
            """
            bool_vec = [x.equals(date, include_ref=self.use_refs, fref=self.ref_comparison_f) and
            x.get_prop_nr() not in del_props for x in tmp_rs]
            """

            if self.debug:
                print("bool_vec: {}".format(bool_vec))
                print('-----------------------------------')
                for x in tmp_rs:
                    if date == x and x.get_prop_nr() not in del_props:
                        print(x.get_prop_nr(), x.get_value(), [z.get_value() for z in x.get_qualifiers()])
                        print(date.get_prop_nr(), date.get_value(), [z.get_value() for z in date.get_qualifiers()])
                    elif x.get_prop_nr() == date.get_prop_nr():
                        print(x.get_prop_nr(), x.get_value(), [z.get_value() for z in x.get_qualifiers()])
                        print(date.get_prop_nr(), date.get_value(), [z.get_value() for z in date.get_qualifiers()])

            if not any(bool_vec):
                if self.debug:
                    print(len(bool_vec))
                    print('fast run failed at', date.get_prop_nr())
                write_required = True
            else:
                if self.debug:
                    print('fast run success')
                tmp_rs.pop(bool_vec.index(True))

        if len(tmp_rs) > 0:
            if self.debug:
                print('failed because not zero')
                for x in tmp_rs:
                    print('xxx', x.get_prop_nr(), x.get_value(), [z.get_value() for z in x.get_qualifiers()])
                print('failed because not zero--END')
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
            data = self._process_lang(result)
            self.loaded_langs[lang].update({lang_data_type: data})

    def get_language_data(self, qid: str, lang: str, lang_data_type: str) -> list:
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

    def check_language_data(self, qid: str, lang_data: list, lang: str, lang_data_type: str,
                            if_exists: str = 'APPEND') -> bool:
        """
        Method to check if certain language data exists as a label, description or aliases
        :param qid: Wikibase item id
        :param lang_data: list of string values to check
        :param lang: language code
        :param lang_data_type: What kind of data is it? 'label', 'description' or 'aliases'?
        :param if_exists: If aliases already exist, APPEND or REPLACE
        :return: boolean
        """
        all_lang_strings = set(x.strip().casefold() for x in self.get_language_data(qid, lang, lang_data_type))

        if if_exists == 'REPLACE':
            return not collections.Counter(all_lang_strings) == collections.Counter(map(lambda x: x.casefold(),
                                                                                        lang_data))
        else:
            for s in lang_data:
                if s.strip().casefold() not in all_lang_strings:
                    if self.debug:
                        print('fastrun failed at: {}, string: {}'.format(lang_data_type, s))
                    return True

        return False

    def get_all_data(self) -> dict:
        return self.prop_data

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
            for value in {'item', 'sid', 'pq', 'pr', 'ref', 'unit', 'qunit'}:
                if value in i:
                    # these are always URIs for the local Wikibase
                    i[value] = i[value]['value'].split('/')[-1]

            # make sure datetimes are formatted correctly.
            # the correct format is '+%Y-%m-%dT%H:%M:%SZ', but is sometimes missing the plus??
            # some difference between RDF and xsd:dateTime that I don't understand
            for value in {'v', 'qval', 'rval'}:
                if value in i:
                    if i[value].get("datatype") == 'http://www.w3.org/2001/XMLSchema#dateTime' and not \
                            i[value]['value'][0] in '+-':
                        # if it is a dateTime and doesn't start with plus or minus, add a plus
                        i[value]['value'] = '+' + i[value]['value']

            # these three ({'v', 'qval', 'rval'}) are values that can be any data type
            # strip off the URI if they are wikibase-items
            if 'v' in i:
                if i['v']['type'] == 'uri' and prop_dt == 'wikibase-item':
                    i['v'] = i['v']['value'].split('/')[-1]
                elif i['v']['type'] == 'literal' and prop_dt == 'quantity':
                    i['v'] = self.format_amount(i['v']['value'])
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
                    i['qval'] = self.format_amount(i['qval']['value'])
                else:
                    i['qval'] = i['qval']['value']

            # handle reference value
            if 'rval' in i:
                ref_prop_dt = self.get_prop_datatype(prop_nr=i['pr'])
                if i['rval']['type'] == 'uri' and ref_prop_dt == 'wikibase-item':
                    i['rval'] = i['rval']['value'].split('/')[-1]
                else:
                    i['rval'] = i['rval']['value']

    @staticmethod
    def format_amount(amount) -> str:
        # Remove .0 by casting to int
        if float(amount) % 1 == 0:
            amount = int(float(amount))

        # Adding prefix + for positive number and 0
        if not str(amount).startswith('+') and float(amount) >= 0:
            amount = str('+{}'.format(amount))

        # return as string
        return str(amount)

    def update_frc_from_query(self, r: list, prop_nr: str) -> None:
        # r is the output of format_query_results
        # this updates the frc from the query (result of _query_data)
        for i in r:
            qid = i['item']
            if qid not in self.prop_data:
                self.prop_data[qid] = {prop_nr: dict()}
            if prop_nr not in self.prop_data[qid]:
                self.prop_data[qid].update({prop_nr: dict()})
            if i['sid'] not in self.prop_data[qid][prop_nr]:
                self.prop_data[qid][prop_nr].update({i['sid']: dict()})
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
                self.prop_data[qid][prop_nr][i['sid']]['ref'] = dict()
            if 'ref' in i:
                if i['ref'] not in self.prop_data[qid][prop_nr][i['sid']]['ref']:
                    self.prop_data[qid][prop_nr][i['sid']]['ref'][i['ref']] = set()
                self.prop_data[qid][prop_nr][i['sid']]['ref'][i['ref']].add((i['pr'], i['rval']))

            if 'unit' not in self.prop_data[qid][prop_nr][i['sid']]:
                self.prop_data[qid][prop_nr][i['sid']]['unit'] = '1'
            if 'unit' in i:
                self.prop_data[qid][prop_nr][i['sid']]['unit'] = i['unit']

    def _query_data(self, prop_nr: str) -> None:
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

            r = wbi_core.FunctionsEngine.execute_sparql_query(query, endpoint=self.sparql_endpoint_url)['results'][
                'bindings']
            count = int(r[0]['c']['value'])
            num_pages = (int(count) // page_size) + 1
            print("Query {}: {}/{}".format(prop_nr, page_count, num_pages))
        while True:
            if self.use_refs:
                query = '''
                    #Tool: wbi_fastrun _query_data_refs
                    SELECT ?sid ?item ?v ?unit ?pq ?qval ?qunit ?ref ?pr ?rval
                    WHERE
                    {{
                      {base_filter}

                      # Get amount and unit for the statement
                      ?item <{wb_url}/prop/{prop_nr}> ?sid .
                      {{
                        <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type .
                        FILTER (?property_type != wikibase:Quantity)
                        ?sid <{wb_url}/prop/statement/{prop_nr}> ?v .
                      }}
                      UNION
                      {{
                        ?sid <{wb_url}/prop/statement/value/{prop_nr}> [wikibase:quantityAmount ?v; wikibase:quantityUnit ?unit] .
                      }}

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

                      # get references
                      OPTIONAL {{
                        ?sid prov:wasDerivedFrom ?ref .
                        ?ref ?pr ?rval .
                        [] wikibase:reference ?pr
                      }}
                    }} ORDER BY ?sid OFFSET {offset} LIMIT {page_size}
                    '''.format(wb_url=self.wikibase_url, base_filter=self.base_filter_string, prop_nr=prop_nr,
                               offset=str(page_count * page_size), page_size=str(page_size))
            else:
                query = '''
                    #Tool: wbi_fastrun _query_data
                    SELECT ?sid ?item ?v ?unit ?pq ?qval ?qunit
                    WHERE
                    {{
                      {base_filter}

                      # Get amount and unit for the statement
                      ?item <{wb_url}/prop/{prop_nr}> ?sid .
                      {{
                        <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type .
                        FILTER (?property_type != wikibase:Quantity)
                        ?sid <{wb_url}/prop/statement/{prop_nr}> ?v .
                      }}
                      UNION
                      {{
                        ?sid <{wb_url}/prop/statement/value/{prop_nr}> [wikibase:quantityAmount ?v; wikibase:quantityUnit ?unit] .
                      }}

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
                    }} ORDER BY ?sid OFFSET {offset} LIMIT {page_size}
                    '''.format(wb_url=self.wikibase_url, base_filter=self.base_filter_string, prop_nr=prop_nr,
                               offset=str(page_count * page_size), page_size=str(page_size))

            if self.debug:
                print(query)

            results = wbi_core.FunctionsEngine.execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)[
                'results']['bindings']
            self.format_query_results(results, prop_nr)
            self.update_frc_from_query(results, prop_nr)
            page_count += 1
            if num_pages:
                print("Query {}: {}/{}".format(prop_nr, page_count, num_pages))
            if len(results) == 0 or len(results) < page_size:
                break

    def _query_lang(self, lang: str, lang_data_type: str) -> None:
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
        #Tool: wbi_fastrun _query_lang
        SELECT ?item ?label WHERE {{
            {base_filter}

            OPTIONAL {{
                ?item {lang_data_type} ?label FILTER (lang(?label) = "{lang}") .
            }}
        }}
        '''.format(base_filter=self.base_filter_string, lang_data_type=lang_data_type_dict[lang_data_type], lang=lang)

        if self.debug:
            print(query)

        return wbi_core.FunctionsEngine.execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results'][
            'bindings']

    @staticmethod
    def _process_lang(result: list) -> set:
        data = defaultdict(set)
        for r in result:
            qid = r['item']['value'].split("/")[-1]
            if 'label' in r:
                data[qid].add(r['label']['value'])
        return data

    @lru_cache(maxsize=100000)
    def get_prop_datatype(self, prop_nr: str) -> str:
        item = self.engine(item_id=prop_nr, sparql_endpoint_url=self.sparql_endpoint_url,
                           mediawiki_api_url=self.mediawiki_api_url,
                           wikibase_url=self.wikibase_url)
        return item.entity_metadata['datatype']

    def clear(self) -> None:
        """
        convinience function to empty this fastrun container
        """
        self.prop_dt_map = dict()
        self.prop_data = dict()
        self.rev_lookup = defaultdict(set)
        self.rev_lookup_ci = defaultdict(set)

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
        )
