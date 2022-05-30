import copy
import unittest

from wikibaseintegrator import WikibaseIntegrator, datatypes, wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, Item
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_fastrun import get_fastrun_container

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_all.py)'

wbi = WikibaseIntegrator()


class TestDataType(unittest.TestCase):
    def test_quantity(self):
        dt = datatypes.Quantity(amount='34.5', prop_nr='P43')

        dt_json = dt.get_json()

        assert dt_json['mainsnak']['datatype'] == 'quantity'

        value = dt_json['mainsnak']['datavalue']

        assert value['value']['amount'] == '+34.5'
        assert value['value']['unit'] == '1'

        dt2 = datatypes.Quantity(amount='34.5', prop_nr='P43', upper_bound='35.3', lower_bound='33.7', unit="Q11573")

        value = dt2.get_json()['mainsnak']['datavalue']

        assert value['value']['amount'] == '+34.5'
        assert value['value']['unit'] == 'http://www.wikidata.org/entity/Q11573'
        assert value['value']['upperBound'] == '+35.3'
        assert value['value']['lowerBound'] == '+33.7'

    def test_geoshape(self):
        dt = datatypes.GeoShape(value='Data:Inner_West_Light_Rail_stops.map', prop_nr='P43')

        dt_json = dt.get_json()

        assert dt_json['mainsnak']['datatype'] == 'geo-shape'

        value = dt_json['mainsnak']['datavalue']

        assert value['value'] == 'Data:Inner_West_Light_Rail_stops.map'

        assert value['type'] == 'string'


class TestFastRun(unittest.TestCase):
    """
    some basic tests for fastrun mode
    """

    def test_fastrun(self):
        statements = [
            datatypes.ExternalID(value='P40095', prop_nr='P352'),
            datatypes.ExternalID(value='YER158C', prop_nr='P705')
        ]

        frc = wbi_fastrun.FastRunContainer(base_filter=[BaseDataType(prop_nr='P352'), datatypes.Item(prop_nr='P703', value='Q27510868')], base_data_type=datatypes.BaseDataType)

        fastrun_result = frc.write_required(data=statements)

        if fastrun_result:
            message = 'fastrun failed'
        else:
            message = 'successful fastrun'

        # here, fastrun should succeed, if not, test failed
        if fastrun_result:
            raise ValueError

    def test_fastrun_label(self):
        # tests fastrun label, description and aliases, and label in another language
        frc = get_fastrun_container(base_filter=[datatypes.ExternalID(value='/m/02j71', prop_nr='P646')])
        item = WikibaseIntegrator().item.get('Q2')

        assert item.labels.get(language='en') == "Earth"
        descr = item.descriptions.get(language='en')
        assert len(descr) > 3
        assert "the Earth" in item.aliases.get()

        assert list(frc.get_language_data("Q2", 'en', 'label'))[0] == item.labels.get(language='en')
        assert frc.check_language_data("Q2", ['not the Earth'], 'en', 'label')
        assert "the Earth" in item.aliases.get()
        assert "planet" in item.descriptions.get()

        assert item.labels.get('es') == "Tierra"

        item.descriptions.set(value=descr)
        item.descriptions.set(value="fghjkl")
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
        item.labels.set(value="Earth")
        item.labels.set(value="xfgfdsg")
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        item.aliases.set(values=["fake alias"], action_if_exists=ActionIfExists.APPEND)
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

        # something that's empty (for now.., can change, so this just makes sure no exception is thrown)
        frc.check_language_data("Q2", ['Ewiase'], 'ak', 'label')
        frc.check_language_data("Q2", ['not Ewiase'], 'ak', 'label')
        frc.check_language_data("Q2", [''], 'ak', 'description')
        frc.check_language_data("Q2", [], 'ak', 'aliases')
        frc.check_language_data("Q2", ['sdf', 'sdd'], 'ak', 'aliases')

        item.labels.get(language="ak")
        item.descriptions.get(language='ak')
        item.aliases.get(language="ak")
        item.labels.set(value="label", language="ak")
        item.descriptions.set(value="d", language="ak")
        item.aliases.set(values=["a"], language="ak", action_if_exists=ActionIfExists.APPEND)


def test_sitelinks():
    item = wbi.item.get('Q622901')
    item.claims.add(datatypes.Item(value='Q12136', prop_nr='P31'))
    assert item.sitelinks.get('enwiki') is not None
    item.sitelinks.set(site="enwiki", title="something")
    assert item.sitelinks.get('enwiki').title == "something"
    assert item.sitelinks.get('enwiki') is not None


def test_nositelinks():
    # this item doesn't and probably won't ever have any sitelinks (but who knows?? maybe one day..)
    item = wbi.item.get('Q27869338')
    item.claims.add(datatypes.Item(value='Q5', prop_nr='P31'))
    assert item.sitelinks.get('enwiki') is None
    item.sitelinks.set(site="enwiki", title="something")
    assert item.sitelinks.get('enwiki').title == "something"
    assert item.sitelinks.get('enwiki') is not None


####
# tests for statement equality, with and without refs
####
def test_ref_equals():
    # statements are identical
    oldref = [datatypes.ExternalID(value='P58742', prop_nr='P352'),
              datatypes.Item(value='Q24784025', prop_nr='P527'),
              datatypes.Time(time='+2001-12-31T00:00:00Z', prop_nr='P813')]
    olditem = datatypes.Item(value='Q123', prop_nr='P123', references=[oldref])
    newitem = copy.deepcopy(olditem)

    assert olditem.equals(newitem, include_ref=False)
    assert olditem.equals(newitem, include_ref=True)

    # dates are a month apart
    newitem = copy.deepcopy(olditem)
    newitem.references.remove(datatypes.Time(time='+2001-12-31T00:00:00Z', prop_nr='P813'))
    newitem.references.add(datatypes.Time(time='+2002-01-31T00:00:00Z', prop_nr='P813'))
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)

    # multiple refs
    newitem = copy.deepcopy(olditem)
    newitem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)
    olditem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
    assert olditem.equals(newitem, include_ref=True)


def test_equal_qualifiers():
    claim1 = Item(prop_nr='P1')
    claim1.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q2')])
    claim2 = Item(prop_nr='P4')
    claim2.qualifiers.set([Item(prop_nr='P2', value='Q1')])
    claim3 = Item(prop_nr='P4')
    claim3.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q2')])
    claim4 = Item(prop_nr='P4')
    claim4.qualifiers.set([Item(prop_nr='P2', value='Q1'), Item(prop_nr='P2', value='Q3')])

    assert claim1.has_equal_qualifiers(claim2) is False
    assert claim1.has_equal_qualifiers(claim3) is True
    assert claim1.has_equal_qualifiers(claim4) is False


def test_mediainfo():
    mediainfo_item_by_title = wbi.mediainfo.get_by_title(titles='File:2018-07-05-budapest-buda-hill.jpg', mediawiki_api_url='https://commons.wikimedia.org/w/api.php')
    assert mediainfo_item_by_title.id == 'M75908279'

    mediainfo_item_by_id = wbi.mediainfo.get(entity_id='M75908279', mediawiki_api_url='https://commons.wikimedia.org/w/api.php')
    assert mediainfo_item_by_id.id == 'M75908279'


def test_wikibaseintegrator():
    nwbi = WikibaseIntegrator(is_bot=False)
    assert nwbi.item.api.is_bot is False
    assert ItemEntity(api=nwbi, is_bot=True).api.is_bot is True
    assert ItemEntity(api=nwbi).api.is_bot is False
    assert ItemEntity().api.is_bot is False
    assert nwbi.item.get('Q582').api.is_bot is False
    assert ItemEntity(api=nwbi, is_bot=True).get('Q582').api.is_bot is True
