"""
Tests for the wbi_enums mirroring API values (#795): WikibaseDatatype, WikibaseRank and WikibaseSnakType members are
also strings, WikibaseTimePrecision members are also integers.
"""
import json

import pytest
import ujson

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import URL, BaseDataType, ExternalID, Item, MonolingualText, String, Time
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
from wikibaseintegrator.models import Claim, Snak
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseRank, WikibaseSnakType, WikibaseTimePrecision


class TestWikibaseDatatype:
    def test_member_is_a_string(self):
        assert WikibaseDatatype.ITEM == 'wikibase-item'
        assert isinstance(WikibaseDatatype.ITEM, str)
        assert str(WikibaseDatatype.ITEM) == 'wikibase-item'
        assert f'{WikibaseDatatype.ITEM}' == 'wikibase-item'
        assert {'wikibase-item': 1}[WikibaseDatatype.ITEM] == 1

    def test_serialization(self):
        assert json.dumps({'datatype': WikibaseDatatype.ITEM}) == '{"datatype": "wikibase-item"}'
        assert ujson.dumps({'datatype': WikibaseDatatype.ITEM}) == '{"datatype":"wikibase-item"}'

    @pytest.mark.parametrize('value, expected', [
        ('wikibase-item', WikibaseDatatype.ITEM),
        (WikibaseDatatype.TIME, WikibaseDatatype.TIME),
        ('localMedia', WikibaseDatatype.LOCALMEDIA),
        (None, None),
    ])
    def test_from_value(self, value, expected):
        assert WikibaseDatatype.from_value(value) is expected

    def test_from_value_keeps_an_unknown_datatype(self):
        """A datatype provided by a Wikibase extension unknown to WikibaseIntegrator is kept as is."""
        result = WikibaseDatatype.from_value('my-extension-datatype')
        assert result == 'my-extension-datatype'
        assert not isinstance(result, WikibaseDatatype)


class TestDatatypeClasses:
    @pytest.mark.parametrize('cls', [subclass for subclass in BaseDataType.subclasses if subclass.DTYPE != BaseDataType.DTYPE])
    def test_dtype_is_a_member(self, cls):
        assert isinstance(cls.DTYPE, WikibaseDatatype)

    @pytest.mark.parametrize('cls, dtype', [
        (String, 'string'), (ExternalID, 'external-id'), (Item, 'wikibase-item'), (URL, 'url'), (Time, 'time'),
        (MonolingualText, 'monolingualtext'), (EDTF, 'edtf'), (LocalMedia, 'localMedia'),
    ])
    def test_dtype_value_is_unchanged(self, cls, dtype):
        assert cls.DTYPE == dtype

    def test_lookup_by_datatype_string(self):
        """The data type classes are still found from the datatype strings of the API."""
        assert [cls for cls in BaseDataType.subclasses if cls.DTYPE == 'wikibase-item'] == [Item]


class TestSnakDatatype:
    def test_known_datatype_is_a_member(self):
        snak = Snak().from_json({'snaktype': 'value', 'property': 'P31', 'datatype': 'wikibase-item',
                                 'datavalue': {'value': {'entity-type': 'item', 'id': 'Q5'}, 'type': 'wikibase-entityid'}})
        assert snak.datatype is WikibaseDatatype.ITEM

    def test_json_holds_a_plain_string(self):
        snak_json = Item(value='Q5', prop_nr='P31').get_json()['mainsnak']
        assert snak_json['datatype'] == 'wikibase-item'
        assert type(snak_json['datatype']) is str  # pylint: disable=unidiomatic-typecheck

    def test_unknown_datatype_is_kept(self):
        snak = Snak().from_json({'snaktype': 'novalue', 'property': 'P1', 'datatype': 'my-extension-datatype'})
        assert snak.datatype == 'my-extension-datatype'
        assert snak.get_json()['datatype'] == 'my-extension-datatype'

    def test_mediainfo_snak_without_datatype(self):
        snak = Snak().from_json({'snaktype': 'novalue', 'property': 'P1'})
        assert snak.datatype is None
        assert 'datatype' not in snak.get_json()

    def test_equality_between_string_and_member(self):
        assert Snak(property_number='P1', datatype='string') == Snak(property_number='P1', datatype=WikibaseDatatype.STRING)

    def test_plain_claim_keeps_its_placeholder_datatype(self):
        assert Claim().mainsnak.datatype == 'claim'


class TestPropertyDatatype:
    def test_known_datatype(self):
        prop = WikibaseIntegrator().property.new(datatype='wikibase-item')
        assert prop.datatype is WikibaseDatatype.ITEM
        assert prop.get_json()['datatype'] == 'wikibase-item'

    def test_unknown_datatype(self, wikibase):
        """A property with a datatype unknown to WikibaseIntegrator can be loaded and written back (it raised a ValueError before)."""
        wikibase.add_property('P51', 'my-extension-datatype')

        prop = WikibaseIntegrator().property.get('P51')

        assert prop.datatype == 'my-extension-datatype'
        assert prop.get_json()['datatype'] == 'my-extension-datatype'

    def test_get_property(self, wikibase):
        wikibase.add_property('P50', 'wikibase-item')
        assert WikibaseIntegrator().property.get('P50').datatype is WikibaseDatatype.ITEM


class TestRankAndSnakType:
    @pytest.mark.parametrize('member, value', [
        (WikibaseRank.DEPRECATED, 'deprecated'), (WikibaseRank.NORMAL, 'normal'), (WikibaseRank.PREFERRED, 'preferred'),
        (WikibaseSnakType.KNOWN_VALUE, 'value'), (WikibaseSnakType.NO_VALUE, 'novalue'), (WikibaseSnakType.UNKNOWN_VALUE, 'somevalue'),
    ])
    def test_member_is_a_string(self, member, value):
        assert member == value
        assert str(member) == value
        assert {value: 1}[member] == 1

    def test_comparison_with_the_json(self):
        claim_json = {'mainsnak': {'snaktype': 'novalue', 'property': 'P1', 'datatype': 'string'}, 'type': 'statement', 'id': 'Q1$abc', 'rank': 'preferred'}
        claim = Claim().from_json(claim_json)

        assert claim.rank == 'preferred'
        assert claim.mainsnak.snaktype == 'novalue'
        assert claim_json['rank'] == WikibaseRank.PREFERRED

    def test_strings_are_accepted(self):
        claim = String(value='abc', prop_nr='P1', rank='deprecated')
        claim.mainsnak.snaktype = 'somevalue'

        assert claim.rank is WikibaseRank.DEPRECATED
        assert claim.mainsnak.snaktype is WikibaseSnakType.UNKNOWN_VALUE

    def test_json_holds_plain_strings(self):
        claim_json = String(value='abc', prop_nr='P1', rank=WikibaseRank.PREFERRED).get_json()

        assert type(claim_json['rank']) is str  # pylint: disable=unidiomatic-typecheck
        assert type(claim_json['mainsnak']['snaktype']) is str  # pylint: disable=unidiomatic-typecheck
        assert ujson.dumps([claim_json['rank'], claim_json['mainsnak']['snaktype']]) == '["preferred","value"]'


class TestTimePrecision:
    def test_member_is_an_integer(self):
        assert WikibaseTimePrecision.DAY == 11
        assert isinstance(WikibaseTimePrecision.YEAR, int)
        assert WikibaseTimePrecision.YEAR < WikibaseTimePrecision.MONTH < WikibaseTimePrecision.DAY
        assert json.dumps(WikibaseTimePrecision.DAY) == '11'

    @pytest.mark.parametrize('precision', [WikibaseTimePrecision.BILLION_YEARS, 0])
    def test_billion_years_precision(self, precision):
        """The precision 0 was ignored when given as an integer, and inferred from the timestamp (year precision)."""
        datavalue = Time(time='-13700000000-00-00T00:00:00Z', precision=precision, prop_nr='P1').get_json()['mainsnak']['datavalue']
        assert datavalue['value']['precision'] == 0

    @pytest.mark.parametrize('time, precision', [('+2021-05-17T00:00:00Z', 11), ('+2021-05-00T00:00:00Z', 10), ('+2021-00-00T00:00:00Z', 9)])
    def test_inferred_precision(self, time, precision):
        datavalue = Time(time=time, prop_nr='P1').get_json()['mainsnak']['datavalue']
        assert datavalue['value']['precision'] == precision
        assert type(datavalue['value']['precision']) is int  # pylint: disable=unidiomatic-typecheck
