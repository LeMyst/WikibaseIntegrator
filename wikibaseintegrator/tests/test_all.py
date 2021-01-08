import copy
import pprint
import unittest

import requests

from wikibaseintegrator import wbi_core, wbi_fastrun
from wikibaseintegrator.wbi_core import MWApiError

__author__ = 'Sebastian Burgstaller-Muehlbacher'
__license__ = 'AGPLv3'


class TestMediawikiApiCall(unittest.TestCase):
    def test_all(self):
        with self.assertRaises(MWApiError):
            wbi_core.FunctionsEngine.mediawiki_api_call("GET", "http://www.wikidataaaaaaa.org", max_retries=3,
                                                        retry_after=1, params={'format': 'json',
                                                                               'action': 'wbgetentities', 'ids': 'Q42'})
        with self.assertRaises(requests.HTTPError):
            wbi_core.FunctionsEngine.mediawiki_api_call("GET", "http://httpbin.org/status/400", max_retries=3,
                                                        retry_after=1)

        wbi_core.FunctionsEngine.mediawiki_api_call("GET", max_retries=3, retry_after=1,
                                                    params={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'})


class TestDataType(unittest.TestCase):
    def test_wd_quantity(self):
        dt = wbi_core.Quantity(quantity='34.5', prop_nr='P43')

        dt_json = dt.get_json_representation()

        if not dt_json['mainsnak']['datatype'] == 'quantity':
            raise

        value = dt_json['mainsnak']['datavalue']

        if not value['value']['amount'] == '+34.5':
            raise

        if not value['value']['unit'] == '1':
            raise

        dt2 = wbi_core.Quantity(quantity='34.5', prop_nr='P43', upper_bound='35.3', lower_bound='33.7', unit="Q11573")

        value = dt2.get_json_representation()['mainsnak']['datavalue']

        if not value['value']['amount'] == '+34.5':
            raise

        if not value['value']['unit'] == 'http://www.wikidata.org/entity/Q11573':
            raise

        if not value['value']['upperBound'] == '+35.3':
            raise

        if not value['value']['lowerBound'] == '+33.7':
            raise

    def test_wd_geoshape(self):
        dt = wbi_core.GeoShape(value='Data:Inner_West_Light_Rail_stops.map', prop_nr='P43')

        dt_json = dt.get_json_representation()

        if not dt_json['mainsnak']['datatype'] == 'geo-shape':
            raise

        value = dt_json['mainsnak']['datavalue']

        if not value['value'] == 'Data:Inner_West_Light_Rail_stops.map':
            raise

        if not value['type'] == 'string':
            raise

    def test_wd_string(self):
        pass

    def test_live_item(self):
        wd_item = wbi_core.ItemEngine(item_id='Q423111')

        mass_statement = [x for x in wd_item.statements if x.get_prop_nr() == 'P2067'].pop()
        pprint.pprint(mass_statement.get_json_representation())

        if not mass_statement:
            raise

            # TODO: get json directly from the API and compare part to ItemEngine


class TestFastRun(unittest.TestCase):
    """
    some basic tests for fastrun mode

    """

    def test_fast_run(self):
        statements = [
            wbi_core.ExternalID(value='P40095', prop_nr='P352'),
            wbi_core.ExternalID(value='YER158C', prop_nr='P705')
        ]

        frc = wbi_fastrun.FastRunContainer(base_filter={'P352': '', 'P703': 'Q27510868'},
                                           base_data_type=wbi_core.BaseDataType, engine=wbi_core.ItemEngine)

        fast_run_result = frc.write_required(data=statements)

        if fast_run_result:
            message = 'fastrun failed'
        else:
            message = 'successful fastrun'
        print(fast_run_result, message)

        # here, fastrun should succeed, if not, test failed
        # if fast_run_result:
        #    raise ValueError

    def test_fastrun_label(self):
        # tests fastrun label, description and aliases, and label in another language
        data = [wbi_core.ExternalID('/m/02j71', 'P646')]
        fast_run_base_filter = {'P361': 'Q18589965'}
        item = wbi_core.ItemEngine(item_id="Q2", data=data, fast_run=True, fast_run_base_filter=fast_run_base_filter)

        frc = wbi_core.ItemEngine.fast_run_store[0]
        frc.debug = True

        assert item.get_label('en') == "Earth"
        descr = item.get_description('en')
        assert len(descr) > 3
        aliases = item.get_aliases()
        assert "Terra" in aliases

        assert list(item.fast_run_container.get_language_data("Q2", 'en', 'label'))[0] == "Earth"
        assert item.fast_run_container.check_language_data("Q2", ['not the Earth'], 'en', 'label')
        assert "Terra" in item.get_aliases()
        assert "planet" in item.get_description()

        assert item.get_label("es") == "Tierra"

        item.set_description(descr)
        item.set_description("fghjkl")
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
        item.set_label("Earth")
        item.set_label("xfgfdsg")
        assert item.json_representation['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        item.set_aliases(["fake alias"], if_exists='APPEND')
        assert {'language': 'en', 'value': 'fake alias'} in item.json_representation['aliases']['en']

        # something thats empty (for now.., can change, so this just makes sure no exception is thrown)
        frc.check_language_data("Q2", ['Ewiase'], 'ak', 'label')
        frc.check_language_data("Q2", ['not Ewiase'], 'ak', 'label')
        frc.check_language_data("Q2", [''], 'ak', 'description')
        frc.check_language_data("Q2", [], 'ak', 'aliases')
        frc.check_language_data("Q2", ['sdf', 'sdd'], 'ak', 'aliases')

        item.get_label("ak")
        item.get_description("ak")
        item.get_aliases("ak")
        item.set_label("label", lang="ak")
        item.set_description("d", lang="ak")
        item.set_aliases(["a"], lang="ak", if_exists='APPEND')


def test_sitelinks():
    data = [wbi_core.ItemID(value='Q12136', prop_nr='P31')]
    item = wbi_core.ItemEngine(item_id='Q622901', data=data)
    item.get_sitelink("enwiki")
    assert "enwiki" not in item.json_representation['sitelinks']
    item.set_sitelink("enwiki", "something")
    assert item.get_sitelink("enwiki")['title'] == "something"
    assert "enwiki" in item.json_representation['sitelinks']


def test_nositelinks():
    # this item doesn't and probably wont ever have any sitelinks (but who knows?? maybe one day..)
    data = [wbi_core.ItemID(value='Q5', prop_nr='P31')]
    item = wbi_core.ItemEngine(item_id='Q27869338', data=data)
    item.get_sitelink("enwiki")
    assert "enwiki" not in item.json_representation['sitelinks']
    item.set_sitelink("enwiki", "something")
    assert item.get_sitelink("enwiki")['title'] == "something"
    assert "enwiki" in item.json_representation['sitelinks']


####
# tests for statement equality, with and without refs
####
def test_ref_equals():
    # statements are identical
    oldref = [wbi_core.ExternalID(value='P58742', prop_nr='P352', is_reference=True),
              wbi_core.ItemID(value='Q24784025', prop_nr='P527', is_reference=True),
              wbi_core.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_reference=True)]
    olditem = wbi_core.ItemID("Q123", "P123", references=[oldref])
    newitem = copy.deepcopy(olditem)
    assert olditem.equals(newitem, include_ref=False)
    assert olditem.equals(newitem, include_ref=True)

    # dates are a month apart
    newitem = copy.deepcopy(olditem)
    newitem.references[0][2] = wbi_core.Time(time='+2002-01-31T12:01:13Z', prop_nr='P813')
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)

    # multiple refs
    newitem = copy.deepcopy(olditem)
    newitem.references.append([wbi_core.ExternalID(value='99999', prop_nr='P352')])
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)
    olditem.references.append([wbi_core.ExternalID(value='99999', prop_nr='P352')])
    assert olditem.equals(newitem, include_ref=True)
