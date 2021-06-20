import copy
import unittest

import requests

from wikibaseintegrator import wbi_fastrun, WikibaseIntegrator, datatypes
from wikibaseintegrator.entities import Item
from wikibaseintegrator.entities.baseentity import MWApiError
from wikibaseintegrator.wbi_api import Api

wbi = WikibaseIntegrator()


class TestMediawikiApiCall(unittest.TestCase):
    def test_all(self):
        with self.assertRaises(MWApiError):
            Api.mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, mediawiki_api_url="https://www.wikidataaaaaaa.org", max_retries=3,
                                          retry_after=1, allow_anonymous=True)
        with self.assertRaises(requests.HTTPError):
            Api.mediawiki_api_call_helper(data=None, mediawiki_api_url="https://httpbin.org/status/400", max_retries=3, retry_after=1, allow_anonymous=True)

        test = Api.mediawiki_api_call_helper(data={'format': 'json', 'action': 'wbgetentities', 'ids': 'Q42'}, max_retries=3, retry_after=1,
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

        frc = wbi_fastrun.FastRunContainer(api=wbi.api, base_filter={'P352': '', 'P703': 'Q27510868'}, base_data_type=datatypes.BaseDataType)

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
        fast_run_base_filter = {'P361': 'Q18589965'}
        wbi_fr = WikibaseIntegrator(debug=True)
        item = Item(fast_run_base_filter=fast_run_base_filter)
        item.claims.add(datatypes.ExternalID('/m/02j71', 'P646'))

        frc = Api.fast_run_store[0]
        frc.debug = True

        assert item.labels.get('en') == "Earth"
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
    oldref = [datatypes.ExternalID(value='P58742', prop_nr='P352', is_reference=True),
              datatypes.Item(value='Q24784025', prop_nr='P527', is_reference=True),
              datatypes.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_reference=True)]
    olditem = datatypes.Item("Q123", "P123", references=[oldref])
    newitem = copy.deepcopy(olditem)
    assert olditem.equals(newitem, include_ref=False)
    assert olditem.equals(newitem, include_ref=True)

    # dates are a month apart
    newitem = copy.deepcopy(olditem)
    newitem.references[0][2] = datatypes.Time(time='+2002-01-31T12:01:13Z', prop_nr='P813')
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)

    # multiple refs
    newitem = copy.deepcopy(olditem)
    newitem.references.append([datatypes.ExternalID(value='99999', prop_nr='P352')])
    assert olditem.equals(newitem, include_ref=False)
    assert not olditem.equals(newitem, include_ref=True)
    olditem.references.append([datatypes.ExternalID(value='99999', prop_nr='P352')])
    assert olditem.equals(newitem, include_ref=True)
