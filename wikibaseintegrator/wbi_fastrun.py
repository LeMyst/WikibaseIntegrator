"""
Fast run mode: check locally, through data loaded from the SPARQL endpoint, whether a write to the Wikibase instance
is actually required, so that a synchronisation bot can skip the entities that are already up to date.
"""
from __future__ import annotations

import collections
import copy
import json
import logging
from collections import defaultdict

from wikibaseintegrator.datatypes import BaseDataType, Time
from wikibaseintegrator.models.claim import Claim
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator.models.qualifiers import Qualifiers
from wikibaseintegrator.models.reference import Reference
from wikibaseintegrator.models.references import References
from wikibaseintegrator.models.snak import Snak
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseRank, WikibaseSnakType
from wikibaseintegrator.wbi_helpers import execute_sparql_query

log = logging.getLogger(__name__)

fastrun_store: list[FastRunContainer] = []

# The RDF export of a Wikibase instance always represents a quantity without a unit ('1' in the JSON representation)
# with the Wikidata entity Q199 (the number one), whatever the instance.
UNITLESS_UNIT_URIS = ('1', 'http://www.wikidata.org/entity/Q199', 'https://www.wikidata.org/entity/Q199')

# The number of statements whose unit and precision are loaded by one SPARQL query
VALUE_DETAILS_BATCH_SIZE = 100


class FastRunContainer:
    """
    A FastRunContainer loads the statements of the entities matching the base filter from the SPARQL endpoint and
    caches them, so that a bot can check whether a write is required without loading every entity through the API.

    :param base_filter: The default filter to initialize the dataset. A list made of BaseDataType or list of BaseDataType.
    :param base_data_type: The default data type to create objects.
    :param use_qualifiers: Use qualifiers during fastrun. Enabled by default.
    :param use_references: Use references during fastrun. Disabled by default.
    :param use_rank: Use rank during fastrun. Disabled by default.
    :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
    :param case_insensitive: Compare the string values without taking the case into account. The comparison of
        qualifiers, references and ranks stays case sensitive. Disabled by default.
    :param sparql_endpoint_url: SPARQL endpoint URL.
    :param wikibase_url: Wikibase URL used for the concept URI.
    """

    data: dict[str, dict[str, list[dict[str, str]]]]

    def __init__(self, base_filter: list[BaseDataType | list[BaseDataType]], base_data_type: type[BaseDataType] | None = None, use_qualifiers: bool = True,
                 use_references: bool = False, use_rank: bool = False, cache: bool = True, case_insensitive: bool = False, sparql_endpoint_url: str | None = None,
                 wikibase_url: str | None = None) -> None:

        for k in base_filter:
            if not isinstance(k, BaseDataType) and not (isinstance(k, list) and len(k) == 2 and isinstance(k[0], BaseDataType) and isinstance(k[1], BaseDataType)):
                raise ValueError("base_filter must be an instance of BaseDataType or a list of instances of BaseDataType")

        # Statements loaded from the SPARQL endpoint: property number -> value key -> list of {'entity': uri, 'sid': uri}
        self.data: dict[str, dict[str, list[dict[str, str]]]] = {}
        # The properties whose statements are completely loaded in self.data. A load restricted to a value or to
        # qualifiers only holds a subset of the statements and must not be reused as a complete cache.
        self.loaded_complete: set[str] = set()

        self.base_filter = base_filter
        self.base_data_type = base_data_type or BaseDataType
        self.sparql_endpoint_url = str(sparql_endpoint_url or config['SPARQL_ENDPOINT_URL'])
        self.wikibase_url = str(wikibase_url or config['WIKIBASE_URL'])
        self.use_qualifiers = use_qualifiers
        self.use_references = use_references
        self.use_rank = use_rank
        self.cache = cache
        self.case_insensitive = case_insensitive
        self.properties_type: dict[str, str] = {}
        self.loaded_langs: dict[str, dict] = {}

        # Per-statement caches for the lazily loaded qualifiers, references and ranks
        self._qualifiers_cache: dict[str, Qualifiers] = {}
        self._references_cache: dict[str, References] = {}
        self._rank_cache: dict[str, WikibaseRank | None] = {}
        # The lazily loaded unit and precision of the values: property number -> statement ID -> (unit, precision).
        # Reset with the statements of the property, so that they are never older than the statements.
        self._value_details: dict[str, dict[str, tuple[str | None, int | None]]] = {}

    @staticmethod
    def _entity_id(entity: str) -> str:
        """Reduce an entity URI to its bare entity ID. A bare entity ID is returned unchanged."""
        return entity.rsplit('/', 1)[-1]

    def _datatype_class(self, property_type: str) -> type[BaseDataType]:
        """
        Return the data type class implementing the given SPARQL property type (e.g. 'http://wikiba.se/ontology#Time' -> Time).

        :param property_type: A property type URI from the wikibase ontology
        :exception ValueError: if no class implements the given property type
        """
        for subclass in self.base_data_type.subclasses:
            if subclass.PTYPE == property_type:
                return subclass
        raise ValueError(f"No data type class found for the property type '{property_type}'")

    @classmethod
    def _normalize_unit(cls, unit: str) -> str:
        """
        Normalize a unit to the format used in the comparison keys: '1' for a unitless quantity (represented by the
        Wikidata Q199 entity in the RDF export, whatever the instance) and the bare entity ID otherwise.

        :param unit: A unit URI from the SPARQL results or from the JSON representation, or '1'
        """
        if unit in UNITLESS_UNIT_URIS:
            return '1'
        return cls._entity_id(unit)

    def _value_key(self, claim: Claim) -> str | None:
        """
        The key indexing the value of the given claim in self.data, casefolded when case_insensitive is enabled.
        An unknown value or no value has no key: it can't be compared through SPARQL.

        The key is the simple value, which holds neither the unit of a quantity nor the precision of a time: two
        amounts only differing by their unit, or '1987' and '1987-01-01', share the same key. They are told apart by
        _filter_value_details().
        """
        if claim.mainsnak.snaktype != WikibaseSnakType.KNOWN_VALUE:
            return None
        value = claim.get_sparql_value()
        if value is None:
            return None
        if self.case_insensitive:
            value = value.casefold()
        return value

    @staticmethod
    def _value_type(claim: Claim) -> str | None:
        """The type of the datavalue of the claim (e.g. 'quantity' or 'time'), or None if it has no datavalue."""
        datavalue = claim.mainsnak.datavalue
        if isinstance(datavalue, dict):
            return datavalue.get('type')
        return None

    def _value_details_from_result(self, result: dict) -> tuple[str | None, int | None]:
        """The normalized unit and the precision of a value, from a SPARQL result binding ?unit and ?precision."""
        unit = self._normalize_unit(result['unit']['value']) if 'unit' in result else None
        precision = int(result['precision']['value']) if 'precision' in result else None
        return unit, precision

    @staticmethod
    def _snak_key(snak: Snak) -> str:
        """
        The key comparing a snak loaded from the SPARQL endpoint with a local snak. The timestamps are compared in the
        form the SPARQL endpoint stores them: '+1987-00-00T00:00:00Z' and '+1987-01-01T00:00:00Z' are the same year.
        """
        datavalue = snak.datavalue
        if isinstance(datavalue, dict) and datavalue.get('type') == 'time':
            datavalue = copy.deepcopy(datavalue)
            datavalue['value']['time'] = Time.sparql_time(datavalue['value']['time'], datavalue['value'].get('precision'))
        return json.dumps([snak.property_number, snak.snaktype.value, snak.datatype, datavalue], sort_keys=True)

    @staticmethod
    def _set_precision(f: BaseDataType, result: dict, name: str) -> None:
        """Set the precision of a time loaded from the SPARQL endpoint, the simple value does not carry it."""
        if name in result and isinstance(f.mainsnak.datavalue, dict) and f.mainsnak.datavalue.get('type') == 'time':
            f.mainsnak.datavalue['value']['precision'] = int(result[name]['value'])

    def _base_filter_string(self, wb_url: str | None = None) -> str:
        """Generate the SPARQL triples restricting ?entity to the entities matching the base filter."""
        wb_url = wb_url or self.wikibase_url

        base_filter_string = ''
        for k in self.base_filter:
            if isinstance(k, BaseDataType):
                # TODO: Add multiple values for a property (OR-operation) (with the VALUES tag?)
                if k.mainsnak.datavalue:
                    base_filter_string += '?entity <{wb_url}/prop/direct/{prop_nr}> {entity} .\n'.format(
                        wb_url=wb_url, prop_nr=k.mainsnak.property_number, entity=k.get_sparql_value(wikibase_url=wb_url))
                elif sum(1 for x in self.base_filter if isinstance(x, BaseDataType) and x.mainsnak.property_number == k.mainsnak.property_number) == 1:
                    base_filter_string += '?entity <{wb_url}/prop/direct/{prop_nr}> ?zz{prop_nr} .\n'.format(
                        wb_url=wb_url, prop_nr=k.mainsnak.property_number)
            elif isinstance(k, list) and len(k) == 2 and isinstance(k[0], BaseDataType) and isinstance(k[1], BaseDataType):
                if k[0].mainsnak.datavalue:
                    base_filter_string += '?entity <{wb_url}/prop/direct/{prop_nr}>/<{wb_url}/prop/direct/{prop_nr2}>* {entity} .\n'.format(
                        wb_url=wb_url, prop_nr=k[0].mainsnak.property_number, prop_nr2=k[1].mainsnak.property_number,
                        entity=k[0].get_sparql_value(wikibase_url=wb_url))
                # TODO: Remove ?zzPYY if another filter have the same property number, the same as above
                else:
                    base_filter_string += '?entity <{wb_url}/prop/direct/{prop_nr1}>/<{wb_url}/prop/direct/{prop_nr2}>* ?zz{prop_nr1}{prop_nr2} .\n'.format(
                        wb_url=wb_url, prop_nr1=k[0].mainsnak.property_number, prop_nr2=k[1].mainsnak.property_number)
            else:
                raise ValueError("base_filter must be an instance of BaseDataType or a list of instances of BaseDataType")

        return base_filter_string

    def load_statements(self, claims: list[Claim] | Claims | Claim, cache: bool | None = None, wb_url: str | None = None, limit: int | None = None) -> None:
        """
        Load the statements related to the given claims into the internal cache of the current object.

        When the cache is enabled, every statement of the property is loaded once and reused afterwards. When the
        cache is disabled and the claim carries a value, only the statements holding the same value (and the same
        qualifiers if use_qualifiers is enabled) are loaded; such a partial load is never reused as a cache.

        A complete load only reads the simple values: joining the value node of every statement, for the unit of a
        quantity or the precision of a time, makes the query of a large dataset exceed the time limit of the SPARQL
        endpoint. The unit and the precision are loaded later, only for the statements holding the value of a claim
        (see _filter_value_details()). A partial load, restricted to one value, reads them directly.

        :param claims: A Claim, Claims or list of Claim
        :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
        :param wb_url: The first part of the concept URI of entities.
        :param limit: The limit to request at one time.
        :return:
        """
        if isinstance(claims, Claim):
            claims = [claims]
        elif (not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims):
            raise ValueError("claims must be an instance of Claim or Claims or a list of Claim")

        if cache is None:
            cache = self.cache

        wb_url = wb_url or self.wikibase_url

        limit = limit or int(config['SPARQL_QUERY_LIMIT'])

        for claim in claims:
            prop_nr = claim.mainsnak.property_number

            # Load each property from the Wikibase instance or the cache
            if cache and prop_nr in self.data and prop_nr in self.loaded_complete:
                log.debug("Property '%s' found in cache, %s elements", prop_nr, len(self.data[prop_nr]))
                continue

            offset = 0

            base_filter_string = self._base_filter_string(wb_url=wb_url)

            # A partial load restricted to the claim value: only when the cache is disabled, because the result
            # can't be reused for other values. The case insensitive mode always needs the complete data, the
            # SPARQL comparison is case sensitive.
            partial_load = bool(claim.mainsnak.datavalue) and not cache and not self.case_insensitive

            # Restrict the statements to the ones holding the same qualifiers as the claim. Only applied to a
            # partial load: a complete load must contain every statement, whatever its qualifiers.
            qualifiers_filter_string = ''
            if partial_load and self.use_qualifiers:
                for qualifier in claim.qualifiers:
                    if not qualifier.datatype:
                        continue
                    fake_json = {
                        'mainsnak': qualifier.get_json(),
                        'type': qualifier.datatype,
                        'id': 'Q0',
                        'rank': 'normal'
                    }
                    f = self.base_data_type.get_datatype_class(qualifier.datatype)().from_json(json_data=fake_json)
                    qualifiers_filter_string += f'?sid <{wb_url}/prop/qualifier/{qualifier.property_number}> {f.get_sparql_value(wikibase_url=wb_url)}.\n'

            # We force a refresh of the data, remove the previous results
            self.data[prop_nr] = {}
            self._value_details[prop_nr] = {}
            self.loaded_complete.discard(prop_nr)

            while True:
                if partial_load:
                    query = '''
                    #Tool: WikibaseIntegrator wbi_fastrun.load_statements
                    SELECT ?entity ?sid ?value ?property_type ?unit ?precision WHERE {{
                      # Base filter string
                      {base_filter_string}
                      ?entity <{wb_url}/prop/{prop_nr}> ?sid.
                      <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type.
                      ?sid <{wb_url}/prop/statement/{prop_nr}> ?value.
                      ?sid <{wb_url}/prop/statement/{prop_nr}> {value}.
                      {qualifiers_filter_string}
                      # The unit of a quantity value, only bound for quantities
                      OPTIONAL {{ ?sid <{wb_url}/prop/statement/value/{prop_nr}> [ wikibase:quantityUnit ?unit ] . }}
                      # The precision of a time value, only bound for times
                      OPTIONAL {{ ?sid <{wb_url}/prop/statement/value/{prop_nr}> [ wikibase:timePrecision ?precision ] . }}
                    }}
                    ORDER BY ?sid
                    OFFSET {offset}
                    LIMIT {limit}
                    '''

                    # Format the query
                    query = query.format(base_filter_string=base_filter_string, wb_url=wb_url, prop_nr=prop_nr, offset=str(offset), limit=str(limit),
                                         value=claim.get_sparql_value(wikibase_url=wb_url), qualifiers_filter_string=qualifiers_filter_string)
                else:
                    # Without the unit and the precision, which are on the value node: see the docstring
                    query = '''
                    #Tool: WikibaseIntegrator wbi_fastrun.load_statements
                    SELECT ?entity ?sid ?value ?property_type WHERE {{
                      # Base filter string
                      {base_filter_string}
                      ?entity <{wb_url}/prop/{prop_nr}> ?sid.
                      <{wb_url}/entity/{prop_nr}> wikibase:propertyType ?property_type.
                      ?sid <{wb_url}/prop/statement/{prop_nr}> ?value.
                    }}
                    ORDER BY ?sid
                    OFFSET {offset}
                    LIMIT {limit}
                    '''

                    # Format the query
                    # TODO: Add custom query support
                    query = query.format(base_filter_string=base_filter_string, wb_url=wb_url, prop_nr=prop_nr, offset=str(offset), limit=str(limit))

                offset += limit  # We increase the offset for the next iteration
                results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

                for result in results:
                    entity = result['entity']['value']
                    sid = result['sid']['value']
                    property_type = result['property_type']['value']

                    try:
                        f = self._datatype_class(property_type)().from_sparql_value(sparql_value=result['value'])
                    except ValueError as exception:
                        # A value the data type can't represent (e.g. a timestamp whose precision can't be inferred).
                        # The value stays out of the dataset, a write will be reported as required for it.
                        log.warning("Skipping a value of property '%s': %s", prop_nr, exception)
                        continue

                    if f is None:
                        # The data type does not implement from_sparql_value() yet
                        log.warning("The data type of property '%s' does not support from_sparql_value(), skipping the value", prop_nr)
                        continue

                    sparql_value = self._value_key(f)
                    if sparql_value is not None:
                        if sparql_value not in self.data[prop_nr]:
                            self.data[prop_nr][sparql_value] = []

                        if prop_nr not in self.properties_type:
                            self.properties_type[prop_nr] = property_type

                        self.data[prop_nr][sparql_value].append({'entity': entity, 'sid': sid})

                        # Only the query of a partial load reads the unit and the precision
                        if partial_load:
                            self._value_details[prop_nr][sid] = self._value_details_from_result(result)

                if len(results) == 0 or len(results) < limit:
                    break

            if not partial_load:
                self.loaded_complete.add(prop_nr)

    def _load_qualifiers(self, sid: str, limit: int | None = None, cache: bool | None = None) -> Qualifiers:
        """
        Load the qualifiers of a statement.

        :param sid: A statement ID.
        :param limit: The limit to request at one time.
        :param cache: Reuse the qualifiers already loaded for this statement. Enabled by default.
        :return: A Qualifiers object.
        """
        if not isinstance(sid, str):
            raise ValueError('sid must be a string')

        if cache is None:
            cache = self.cache

        if cache and sid in self._qualifiers_cache:
            return self._qualifiers_cache[sid]

        offset = 0

        limit = limit or int(config['SPARQL_QUERY_LIMIT'])

        qualifiers: Qualifiers = Qualifiers()
        while True:
            query = f'''
            #Tool: WikibaseIntegrator wbi_fastrun._load_qualifiers
            SELECT ?property ?value ?property_type ?precision WHERE {{
              VALUES ?sid {{ <{sid}> }}
              ?sid ?predicate ?value.
              ?property wikibase:qualifier ?predicate.
              ?property wikibase:propertyType ?property_type.
              # The precision of a time value, from the value node holding the same timestamp
              OPTIONAL {{
                ?property wikibase:qualifierValue ?value_predicate.
                ?sid ?value_predicate ?value_node.
                ?value_node wikibase:timeValue ?value;
                            wikibase:timePrecision ?precision.
              }}
            }}
            ORDER BY ?sid
            OFFSET {offset}
            LIMIT {limit}
            '''

            offset += limit  # We increase the offset for the next iteration
            results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

            for result in results:
                prop_nr = self._entity_id(result['property']['value'])
                property_type = result['property_type']['value']

                if prop_nr not in self.properties_type:
                    self.properties_type[prop_nr] = property_type

                try:
                    f = self._datatype_class(property_type)(prop_nr=prop_nr).from_sparql_value(sparql_value=result['value'])
                except ValueError as exception:
                    # An unparsable qualifier can't be compared, leave it out so that the comparison fails safely
                    log.warning("Skipping a qualifier of statement '%s': %s", sid, exception)
                    continue

                if f is None:
                    log.warning("The data type of property '%s' does not support from_sparql_value(), skipping the qualifier", prop_nr)
                    continue

                self._set_precision(f, result, 'precision')

                qualifiers.add(f)

            if len(results) == 0 or len(results) < limit:
                break

        self._qualifiers_cache[sid] = qualifiers

        return qualifiers

    def _load_references(self, sid: str, limit: int | None = None, cache: bool | None = None) -> References:
        """
        Load the references of a statement.

        :param sid: A statement ID.
        :param limit: The limit to request at one time.
        :param cache: Reuse the references already loaded for this statement. Enabled by default.
        :return: A References object.
        """
        if not isinstance(sid, str):
            raise ValueError('sid must be a string')

        if cache is None:
            cache = self.cache

        if cache and sid in self._references_cache:
            return self._references_cache[sid]

        offset = 0

        limit = limit or int(config['SPARQL_QUERY_LIMIT'])

        # The references are grouped by reference node URI, across the result pages
        reference: dict[str, Reference] = {}
        while True:
            query = f'''
            #Tool: WikibaseIntegrator wbi_fastrun._load_references
            SELECT ?srid ?ref_property ?ref_value ?property_type ?ref_precision WHERE {{
              VALUES ?sid {{ <{sid}> }}

              ?sid prov:wasDerivedFrom ?srid.
              ?srid ?ref_predicate ?ref_value.
              ?ref_property wikibase:reference ?ref_predicate.
              ?ref_property wikibase:propertyType ?property_type.
              # The precision of a time value, from the value node holding the same timestamp
              OPTIONAL {{
                ?ref_property wikibase:referenceValue ?ref_value_predicate.
                ?srid ?ref_value_predicate ?ref_value_node.
                ?ref_value_node wikibase:timeValue ?ref_value;
                                wikibase:timePrecision ?ref_precision.
              }}
            }}
            ORDER BY ?srid
            OFFSET {offset}
            LIMIT {limit}
            '''

            offset += limit  # We increase the offset for the next iteration
            results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

            for result in results:
                prop_nr = self._entity_id(result['ref_property']['value'])
                srid = result['srid']['value']
                property_type = result['property_type']['value']

                if prop_nr not in self.properties_type:
                    self.properties_type[prop_nr] = property_type

                try:
                    f = self._datatype_class(property_type)(prop_nr=prop_nr).from_sparql_value(sparql_value=result['ref_value'])
                except ValueError as exception:
                    # An unparsable reference snak can't be compared, leave it out so that the comparison fails safely
                    log.warning("Skipping a reference snak of statement '%s': %s", sid, exception)
                    continue

                if f is None:
                    log.warning("The data type of property '%s' does not support from_sparql_value(), skipping the reference snak", prop_nr)
                    continue

                self._set_precision(f, result, 'ref_precision')

                if srid not in reference:
                    reference[srid] = Reference()

                reference[srid].add(f)

            if len(results) == 0 or len(results) < limit:
                break

        references: References = References()
        for _, ref in reference.items():
            references.add(ref)

        self._references_cache[sid] = references

        return references

    def _load_rank(self, sid: str, cache: bool | None = None) -> WikibaseRank | None:
        """
        Load the rank of a statement.

        :param sid: A statement ID.
        :param cache: Reuse the rank already loaded for this statement. Enabled by default.
        :return: The WikibaseRank of the statement or None if the statement is not found.
        """
        if not isinstance(sid, str):
            raise ValueError('sid must be a string')

        if cache is None:
            cache = self.cache

        if cache and sid in self._rank_cache:
            return self._rank_cache[sid]

        query = f'''
        #Tool: WikibaseIntegrator wbi_fastrun._load_rank
        SELECT ?rank WHERE {{
          VALUES ?sid {{ <{sid}> }}
          ?sid wikibase:rank ?rank.
        }}
        '''

        results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

        rank: WikibaseRank | None = None
        for result in results:
            rank_raw = result['rank']['value'].rsplit('#', 1)[-1]

            if rank_raw == 'PreferredRank':
                rank = WikibaseRank.PREFERRED
            elif rank_raw == 'NormalRank':
                rank = WikibaseRank.NORMAL
            elif rank_raw == 'DeprecatedRank':
                rank = WikibaseRank.DEPRECATED

        self._rank_cache[sid] = rank

        return rank

    def _load_value_details(self, prop_nr: str, sids: list[str]) -> None:
        """
        Load the unit (of a quantity) and the precision (of a time) of the values of the given statements, which are
        on the value node, not on the simple value loaded by load_statements(). The statements already known are not
        queried again.

        :param prop_nr: The property of the statements.
        :param sids: The statement IDs.
        """
        details = self._value_details.setdefault(prop_nr, {})
        missing = [sid for sid in dict.fromkeys(sids) if sid not in details]

        for start in range(0, len(missing), VALUE_DETAILS_BATCH_SIZE):
            batch = missing[start:start + VALUE_DETAILS_BATCH_SIZE]
            values = ' '.join(f'<{sid}>' for sid in batch)
            query = f'''
            #Tool: WikibaseIntegrator wbi_fastrun._load_value_details
            SELECT ?sid ?unit ?precision WHERE {{
              VALUES ?sid {{ {values} }}
              ?sid ?value_predicate ?value_node.
              ?property wikibase:statementValue ?value_predicate.
              # The unit of a quantity value, only bound for quantities
              OPTIONAL {{ ?value_node wikibase:quantityUnit ?unit . }}
              # The precision of a time value, only bound for times
              OPTIONAL {{ ?value_node wikibase:timePrecision ?precision . }}
            }}
            '''

            results = execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

            # A statement without a value node has neither unit nor precision: its value won't match any claim
            for sid in batch:
                details[sid] = (None, None)
            for result in results:
                details[result['sid']['value']] = self._value_details_from_result(result)

    def _statements_with_value(self, claim: Claim) -> list[dict[str, str]]:
        """The loaded statements holding the simple value of the claim, whatever the unit or the precision of the value."""
        value_key = self._value_key(claim)
        if value_key is None:
            return []
        return list(self.data.get(claim.mainsnak.property_number, {}).get(value_key, []))

    def _filter_value_details(self, claim: Claim, statements: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Keep the statements whose value has the same unit as the claim, for a quantity, or the same precision, for a
        time. The statements of the other data types are returned unchanged.

        The unit and the precision are loaded for the given statements only: pass the statements holding the value of
        the claim, restricted as much as possible (e.g. to the entities holding the other claims).

        :param claim: The claim.
        :param statements: Statements holding the simple value of the claim, from self.data.
        :return: The matching statements.
        """
        value_type = self._value_type(claim)
        if value_type not in ('quantity', 'time') or not statements:
            return statements

        prop_nr = claim.mainsnak.property_number
        self._load_value_details(prop_nr, [statement['sid'] for statement in statements])
        details = self._value_details[prop_nr]
        datavalue = claim.mainsnak.datavalue

        if value_type == 'quantity':
            unit = self._normalize_unit(datavalue['value'].get('unit', '1'))
            return [statement for statement in statements if details[statement['sid']][0] == unit]

        # The simple value of a time drops the precision: '1987' and '1987-01-01' share the same timestamp
        precision = datavalue['value'].get('precision')
        return [statement for statement in statements if details[statement['sid']][1] == precision]

    def get_entities(self, claims: list[Claim] | Claims | Claim, cache: bool | None = None, query_limit: int | None = None) -> list[str]:
        """
        Return a list of entities who correspond to the specified claims.

        :param claims: A list of claims to query the SPARQL endpoint.
        :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
        :param query_limit: Limit the amount of results from the SPARQL server
        :return: A list of entity ID.
        """
        if isinstance(claims, Claim):
            claims = [claims]
        elif (not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims):
            raise ValueError("claims must be an instance of Claim or Claims or a list of Claim")

        if len(claims) == 0:
            raise ValueError("claims must have at least one claim")

        candidates: list[tuple[Claim, list[dict[str, str]]]] = []
        for claim in claims:
            self.load_statements(claims=claim, cache=cache, limit=query_limit)
            candidates.append((claim, self._statements_with_value(claim)))

        # The entities holding every simple value, then among them only, the ones with the same unit or precision
        entities = set.intersection(*({self._entity_id(statement['entity']) for statement in statements} for _, statements in candidates))
        for claim, statements in candidates:
            statements = self._filter_value_details(claim, [statement for statement in statements if self._entity_id(statement['entity']) in entities])
            entities = {self._entity_id(statement['entity']) for statement in statements}

        return sorted(entities)

    def _statement_matches(self, claim: Claim, sid: str, use_qualifiers: bool, use_references: bool, use_rank: bool, cache: bool | None = None) -> bool:
        """
        Deeply compare a statement of the Wikibase instance with a local claim holding the same value.

        :param claim: The local claim.
        :param sid: The statement ID of the statement of the Wikibase instance.
        :param use_qualifiers: Compare the qualifiers.
        :param use_references: Compare the references.
        :param use_rank: Compare the rank.
        :param cache: Reuse the qualifiers, references and rank already loaded for this statement. Enabled by default.
        :return: True if the statement matches the claim.
        """
        if use_qualifiers:
            qualifiers = self._load_qualifiers(sid, cache=cache)

            if qualifiers.count() != claim.qualifiers.count():
                log.debug("Difference in number of qualifiers, '%i' != '%i'", qualifiers.count(), claim.qualifiers.count())
                return False

            if collections.Counter(map(self._snak_key, qualifiers)) != collections.Counter(map(self._snak_key, claim.qualifiers)):
                log.debug("Difference between two qualifiers")
                return False

        if use_references:
            references = self._load_references(sid, cache=cache)

            if len(references) != len(claim.references):
                log.debug("Difference in number of references, '%i' != '%i'", len(references), len(claim.references))
                return False

            # A reference is compared through its snaks, whatever their order
            def reference_key(reference: Reference) -> tuple[str, ...]:
                return tuple(sorted(map(self._snak_key, reference)))

            if collections.Counter(map(reference_key, references)) != collections.Counter(map(reference_key, claim.references)):
                log.debug("Difference between two references")
                return False

        if use_rank:
            rank = self._load_rank(sid, cache=cache)

            if claim.rank != rank:
                log.debug("Difference with the rank")
                return False

        return True

    def write_required(self, claims: list[Claim] | Claims | Claim, entity_filter: list[str] | str | None = None, property_filter: list[str] | str | None = None,
                       action_if_exists: ActionIfExists = ActionIfExists.REPLACE_ALL, use_qualifiers: bool | None = None, use_references: bool | None = None,
                       use_rank: bool | None = None, cache: bool | None = None, query_limit: int | None = None) -> bool:
        """
        Check if a write to the Wikibase instance is required: a write is not required only when at least one entity
        already holds, for every claim, a statement with the same value (and the same qualifiers, references and rank,
        depending on the flags).

        :param claims: The claims proposed to be written.
        :param entity_filter: Allows you to filter the entities checked. This can be a single entity or a list of entities.
            Pass the ID of the entity being edited to check whether this entity specifically already holds the data.
        :param property_filter: Allows you to limit the difference comparison to a list of properties. Claims whose
            property is not in the filter are ignored.
        :param action_if_exists: The action that will be used for the write. With FORCE_APPEND, the statements are
            always appended and a write is always required. The other actions check that the claims already exist.
        :param use_qualifiers: Use qualifiers during fastrun. Enabled by default.
        :param use_references: Use references during fastrun. Disabled by default.
        :param use_rank: Use rank during fastrun. Disabled by default.
        :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
        :param query_limit: Limit the amount of results from the SPARQL server
        :return: a boolean True if a write is required. False otherwise.
        """

        if isinstance(claims, Claim):
            claims = [claims]
        elif (not isinstance(claims, list) or not all(isinstance(n, Claim) for n in claims)) and not isinstance(claims, Claims):
            raise ValueError("claims must be an instance of Claim or Claims or a list of Claim")

        if len(claims) == 0:
            raise ValueError("claims must have at least one claim")

        if action_if_exists == ActionIfExists.FORCE_APPEND:
            # The new statements are always appended, a write is always required
            log.debug("Force append: write required")
            return True

        entities_allowed: set[str] | None = None
        if entity_filter is not None:
            if isinstance(entity_filter, str):
                entity_filter = [entity_filter]
            entities_allowed = {self._entity_id(entity) for entity in entity_filter}

        if property_filter is not None and isinstance(property_filter, str):
            property_filter = [property_filter]

        # Generate a property_filter if None is given
        if property_filter is None:
            property_filter = [claim.mainsnak.property_number for claim in claims]

        if use_qualifiers is None:
            use_qualifiers = self.use_qualifiers
        if use_references is None:
            use_references = self.use_references
        if use_rank is None:
            use_rank = self.use_rank

        claims_to_check = [claim for claim in claims if claim.mainsnak.property_number in property_filter]
        if not claims_to_check:
            # Nothing can be verified through the fastrun data
            log.debug("No claim matches the property filter: write required")
            return True

        # Find, for each claim, the statements holding the same simple value
        candidates: list[tuple[Claim, list[dict[str, str]]]] = []
        for claim in claims_to_check:
            self.load_statements(claims=claim, cache=cache, limit=query_limit)

            statements = self._statements_with_value(claim)
            if entities_allowed is not None:
                statements = [statement for statement in statements if self._entity_id(statement['entity']) in entities_allowed]

            if not statements:
                # Not claim.get_sparql_value(): the arguments are evaluated even without debug logging, and get_sparql_value() of
                # most data types raises without a known value
                log.debug("Value '%s' does not exist for property '%s'", self._value_key(claim), claim.mainsnak.property_number)
                return True

            candidates.append((claim, statements))

        # The entities holding every simple value, then among them only, the ones with the same unit or precision
        common_entities = set.intersection(*({self._entity_id(statement['entity']) for statement in statements} for _, statements in candidates))
        if common_entities:
            candidates = [(claim, self._filter_value_details(claim, [statement for statement in statements if self._entity_id(statement['entity']) in common_entities]))
                          for claim, statements in candidates]
            common_entities = set.intersection(*({self._entity_id(statement['entity']) for statement in statements} for _, statements in candidates))
        if not common_entities:
            log.debug("No entity holds all the claim values: write required")
            return True

        # Deep comparison: no write is needed if at least one entity holds, for every claim, a statement also
        # matching the qualifiers, references and rank, depending on the flags
        for entity in sorted(common_entities):
            for claim, statements in candidates:
                entity_statements = [statement for statement in statements if self._entity_id(statement['entity']) == entity]
                if not any(self._statement_matches(claim, statement['sid'], use_qualifiers=use_qualifiers, use_references=use_references, use_rank=use_rank, cache=cache)
                           for statement in entity_statements):
                    break
            else:
                log.debug("Entity '%s' already holds all the claims: no write required", entity)
                return False

        return True

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

        :param qid: entity ID
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
        all_lang_strings = list(current_lang_data.get(self._entity_id(qid), []))
        if not all_lang_strings and lang_data_type in {'label', 'description'}:
            all_lang_strings = ['']
        return all_lang_strings

    def check_language_data(self, qid: str, lang_data: list, lang: str, lang_data_type: str, action_if_exists: ActionIfExists = ActionIfExists.APPEND_OR_REPLACE) -> bool:
        """
        Method to check if certain language data exists as a label, description or aliases

        :param qid: entity ID
        :param lang_data: list of string values to check
        :param lang: language code
        :param lang_data_type: What kind of data is it? 'label', 'description' or 'aliases'?
        :param action_if_exists: If aliases already exist, APPEND_OR_REPLACE or REPLACE_ALL
        :return: boolean True if a write is required
        """
        all_lang_strings = {x.strip().casefold() for x in self.get_language_data(qid, lang, lang_data_type)}

        if action_if_exists == ActionIfExists.REPLACE_ALL:
            return collections.Counter(all_lang_strings) != collections.Counter(map(lambda x: x.casefold(), lang_data))

        for s in lang_data:
            if s.strip().casefold() not in all_lang_strings:
                log.debug("fastrun failed at: %s, string: %s", lang_data_type, s)
                return True

        return False

    def _query_lang(self, lang: str, lang_data_type: str) -> list[dict[str, dict]] | None:
        """
        Query the SPARQL endpoint for the language data of the entities matching the base filter.

        :param lang: language code
        :param lang_data_type: 'label', 'description' or 'aliases'
        """

        lang_data_type_dict = {
            'label': 'rdfs:label',
            'description': 'schema:description',
            'aliases': 'skos:altLabel'
        }

        query = f'''
        #Tool: WikibaseIntegrator wbi_fastrun._query_lang
        SELECT ?entity ?label WHERE {{
            {self._base_filter_string()}

            OPTIONAL {{
                ?entity {lang_data_type_dict[lang_data_type]} ?label FILTER (lang(?label) = "{lang}") .
            }}
        }}
        '''

        log.debug(query)

        return execute_sparql_query(query=query, endpoint=self.sparql_endpoint_url)['results']['bindings']

    @staticmethod
    def _process_lang(result: list) -> defaultdict[str, set]:
        data = defaultdict(set)
        for r in result:
            qid = r['entity']['value'].split("/")[-1]
            if 'label' in r:
                data[qid].add(r['label']['value'])
        return data

    def clear(self) -> None:
        """
        Convenience function to empty the caches of this fastrun container.
        """
        self.data = {}
        self.loaded_complete = set()
        self.properties_type = {}
        self.loaded_langs = {}
        self._qualifiers_cache = {}
        self._references_cache = {}
        self._rank_cache = {}
        self._value_details = {}

    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


def get_fastrun_container(base_filter: list[BaseDataType | list[BaseDataType]], use_qualifiers: bool = True, use_references: bool = False, use_rank: bool = False,
                          cache: bool = True, case_insensitive: bool = False) -> FastRunContainer:
    """
    Return a FastRunContainer object, create a new one if it doesn't already exist.

    :param base_filter: The default filter to initialize the dataset. A list made of BaseDataType or list of BaseDataType.
    :param use_qualifiers: Use qualifiers during fastrun. Enabled by default.
    :param use_references: Use references during fastrun. Disabled by default.
    :param use_rank: Use rank during fastrun. Disabled by default.
    :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
    :param case_insensitive: Compare the string values without taking the case into account. Disabled by default.
    :return: a FastRunContainer object
    """
    if base_filter is None:
        base_filter = []

    # We search if we already have a FastRunContainer with the same parameters to reuse it
    fastrun_container = _search_fastrun_store(base_filter=base_filter, use_qualifiers=use_qualifiers, use_references=use_references, use_rank=use_rank,
                                              case_insensitive=case_insensitive, cache=cache)

    return fastrun_container


def _search_fastrun_store(base_filter: list[BaseDataType | list[BaseDataType]], use_qualifiers: bool = True, use_references: bool = False, use_rank: bool = False,
                          cache: bool = True, case_insensitive: bool = False) -> FastRunContainer:
    """
    Search for an existing FastRunContainer with the same parameters or create a new one if it doesn't exist.

    :param base_filter: The default filter to initialize the dataset. A list made of BaseDataType or list of BaseDataType.
    :param use_qualifiers: Use qualifiers during fastrun. Enabled by default.
    :param use_references: Use references during fastrun. Disabled by default.
    :param use_rank: Use rank during fastrun. Disabled by default.
    :param cache: Put data returned by the SPARQL endpoint in cache. Enabled by default.
    :param case_insensitive: Compare the string values without taking the case into account. Disabled by default.
    :return: a FastRunContainer object
    """
    for fastrun in fastrun_store:
        if (fastrun.base_filter == base_filter) and (fastrun.use_qualifiers == use_qualifiers) and (fastrun.use_references == use_references) and (
                fastrun.use_rank == use_rank) and (fastrun.case_insensitive == case_insensitive) and (fastrun.sparql_endpoint_url == config['SPARQL_ENDPOINT_URL']):
            fastrun.cache = cache
            return fastrun

    # In case nothing was found in the fastrun_store
    log.info("Create a new FastRunContainer")

    fastrun_container = FastRunContainer(base_data_type=BaseDataType, base_filter=base_filter, use_qualifiers=use_qualifiers, use_references=use_references, use_rank=use_rank,
                                         cache=cache, case_insensitive=case_insensitive)
    fastrun_store.append(fastrun_container)
    return fastrun_container
