"""
Tests for wbi_enums.WikibaseDatatype (#795): the datatypes are enum members that remain usable as strings.
"""
import json

import pytest
import ujson

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import URL, BaseDataType, ExternalID, Item, MonolingualText, String, Time
from wikibaseintegrator.datatypes.extra import EDTF, LocalMedia
from wikibaseintegrator.models import Claim, Snak
from wikibaseintegrator.wbi_enums import WikibaseDatatype


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
