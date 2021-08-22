import copy
import unittest

import requests

from wikibaseintegrator import wbi_fastrun, WikibaseIntegrator, datatypes
from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.entities.baseentity import MWApiError
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

config['DEBUG'] = True

wbi = WikibaseIntegrator()


class TestMediawikiApiCall(unittest.TestCase):
    def test_all(self):
        with self.assertRaises(MWApiError):
            mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=3,
                                      retry_after=1, allow_anonymous=True)
        with self.assertRaises(requests.HTTPError):
            mediawiki_api_call_helper(data=None, mediawiki_api_url="https://httpbin.org/status/400", max_retries=3, retry_after=1, allow_anonymous=True)

        test = mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1,
                                         allow_anonymous=True)
        print(test)


class TestDataType(unittest.TestCase):
    def test_quantity(self):
        dt = datatypes.Quantity(quantity='34.5', prop_nr='P43')

        dt_json = dt.get_json()

        if not dt_json['mainsnak']['datatype'] == 'quantity':
            raise

        value = dt_json['mainsnak']['datavalue']

        if not value['value']['amount'] == '+34.5':
            raise

        if not value['value']['unit'] == '1':
            raise

        dt2 = datatypes.Quantity(quantity='34.5', prop_nr='P43', upper_bound='35.3', lower_bound='33.7', unit="Q11573")

        value = dt2.get_json()['mainsnak']['datavalue']

        if not value['value']['amount'] == '+34.5':
            raise

        if not value['value']['unit'] == 'http://www.wikidata.org/entity/Q11573':
            raise

        if not value['value']['upperBound'] == '+35.3':
            raise

        if not value['value']['lowerBound'] == '+33.7':
            raise

    def test_geoshape(self):
        dt = datatypes.GeoShape(value='Data:Inner_West_Light_Rail_stops.map', prop_nr='P43')

        dt_json = dt.get_json()

        if not dt_json['mainsnak']['datatype'] == 'geo-shape':
            raise

        value = dt_json['mainsnak']['datavalue']

        if not value['value'] == 'Data:Inner_West_Light_Rail_stops.map':
            raise

        if not value['type'] == 'string':
            raise


class TestFastRun(unittest.TestCase):
    """
    some basic tests for fastrun mode
    """

    def test_fast_run(self):
        statements = [
            datatypes.ExternalID(value='P40095', prop_nr='P352'),
            datatypes.ExternalID(value='YER158C', prop_nr='P705')
        ]

        frc = wbi_fastrun.FastRunContainer(base_filter={'P352': '', 'P703': 'Q27510868'}, base_data_type=datatypes.BaseDataType)

        fast_run_result = frc.write_required(data=statements)

        if fast_run_result:
            message = 'fastrun failed'
        else:
            message = 'successful fastrun'
        print(fast_run_result, message)

        # here, fastrun should succeed, if not, test failed
        if fast_run_result:
            raise ValueError

    def test_fastrun_label(self):
        # tests fastrun label, description and aliases, and label in another language
        fast_run_base_filter = {'P361': 'Q18589965'}
        item = WikibaseIntegrator().item.get('Q2')
        item.init_fastrun(base_filter=fast_run_base_filter)
        item.init_fastrun(base_filter=fast_run_base_filter)  # Test if we found the same FastRunContainer
        item.claims.add(datatypes.ExternalID(value='/m/02j71', prop_nr='P646'))

        frc = wbi_fastrun.FastRunContainer(base_filter={'P699': ''}, base_data_type=BaseDataType)

        assert item.labels.get(language='en') == "Earth"
        descr = item.descriptions.get(language='en')
        assert len(descr) > 3
        assert "Terra" in item.aliases.get()

        assert list(item.fast_run_container.get_language_data("Q2", 'en', 'label'))[0] == "Earth"
        assert item.fast_run_container.check_language_data("Q2", ['not the Earth'], 'en', 'label')
        assert "Terra" in item.aliases.get()
        assert "planet" in item.descriptions.get()

        assert item.labels.get('es') == "Tierra"

        item.descriptions.set(value=descr)
        item.descriptions.set(value="fghjkl")
        assert item.get_json()['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
        item.labels.set(value="Earth")
        item.labels.set(value="xfgfdsg")
        assert item.get_json()['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        item.aliases.set(values=["fake alias"], if_exists=ActionIfExists.APPEND)
        assert {'language': 'en', 'value': 'fake alias'} in item.get_json()['aliases']['en']

        # something thats empty (for now.., can change, so this just makes sure no exception is thrown)
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
        item.aliases.set(values=["a"], language="ak", if_exists=ActionIfExists.APPEND)


def test_sitelinks():
    item = wbi.item.get('Q622901')
    item.claims.add(datatypes.Item(value='Q12136', prop_nr='P31'))
    assert item.sitelinks.get('enwiki') is not None
    item.sitelinks.set(site="enwiki", title="something")
    assert item.sitelinks.get('enwiki').title == "something"
    assert item.sitelinks.get('enwiki') is not None


def test_nositelinks():
    # this item doesn't and probably wont ever have any sitelinks (but who knows?? maybe one day..)
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
              datatypes.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813')]
    olditem = datatypes.Item(value='Q123', prop_nr='P123', references=[oldref])
    newitem = copy.deepcopy(olditem)

    assert olditem.equals(newitem, include_ref=False)
    assert olditem.equals(newitem, include_ref=True)

    # dates are a month apart
    newitem = copy.deepcopy(olditem)
    newitem.references.remove(datatypes.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813'))
    newitem.references.add(datatypes.Time(time='+2002-01-31T12:01:13Z', prop_nr='P813'))
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)

    # multiple refs
    newitem = copy.deepcopy(olditem)
    newitem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)
    olditem.references.add(datatypes.ExternalID(value='99999', prop_nr='P352'))
    assert olditem.equals(newitem, include_ref=True)


def test_mediainfo():
    mediainfo_item_by_title = wbi.mediainfo.get_by_title(title='File:2018-07-05-budapest-buda-hill.jpg', mediawiki_api_url='https://commons.wikimedia.org/w/api.php')
    assert mediainfo_item_by_title.id == 'M75908279'

    mediainfo_item_by_id = wbi.mediainfo.get(entity_id='M75908279', mediawiki_api_url='https://commons.wikimedia.org/w/api.php')
    assert mediainfo_item_by_id.id == 'M75908279'
