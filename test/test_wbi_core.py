import unittest

from wikibaseintegrator import wbi_core


class TestWbiCore(unittest.TestCase):
    common_item = wbi_core.ItemEngine(item_id="Q2")

    def test_item_engine(self):
        wbi_core.ItemEngine(debug=True)
        wbi_core.ItemEngine(data=None, debug=True)
        wbi_core.ItemEngine(data=wbi_core.String(value='test', prop_nr='P1'), debug=True)
        wbi_core.ItemEngine(data=[wbi_core.String(value='test', prop_nr='P1')], debug=True)
        with self.assertRaises(TypeError):
            wbi_core.ItemEngine(data='test', debug=True)
        with self.assertRaises(ValueError):
            wbi_core.ItemEngine(fast_run_case_insensitive=True, debug=True)
        with self.assertRaises(TypeError):
            wbi_core.ItemEngine(ref_handler='test', debug=True)
        with self.assertRaises(ValueError):
            wbi_core.ItemEngine(global_ref_mode='CUSTOM', debug=True)
        wbi_core.ItemEngine(item_id='Q2', fast_run=True, debug=True)

    def test_search_only(self):
        item = wbi_core.ItemEngine(item_id="Q2", search_only=True)

        assert item.get_label('en') == "Earth"
        descr = item.get_description('en')
        assert len(descr) > 3

        assert "Terra" in item.get_aliases()
        assert "planet" in item.get_description()

        assert item.get_label("es") == "Tierra"

    def test_basedatatype_if_exists(self):
        instance_of_append = wbi_core.ItemID(prop_nr='P31', value='Q1234', if_exists='APPEND')
        instance_of_forceappend = wbi_core.ItemID(prop_nr='P31', value='Q3504248', if_exists='FORCE_APPEND')
        instance_of_replace = wbi_core.ItemID(prop_nr='P31', value='Q1234', if_exists='REPLACE')
        instance_of_keep = wbi_core.ItemID(prop_nr='P31', value='Q1234', if_exists='KEEP')

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_append, instance_of_append])
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) > 1 and 'Q1234' in claims and claims.count('Q1234') == 1

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_forceappend, instance_of_forceappend])
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) > 1 and 'Q3504248' in claims and claims.count('Q3504248') == 3

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_replace], debug=True)
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31'] if 'remove' not in x]
        removed_claims = [True for x in item.get_json_representation()['claims']['P31'] if 'remove' in x]
        assert len(claims) == 1 and 'Q1234' in claims and len(removed_claims) == 1 and True in removed_claims

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_keep], debug=True)
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) == 1 and 'Q1234' not in claims

    def test_label(self):
        item = wbi_core.ItemEngine(item_id="Q2")

        assert item.get_label('en') == "Earth"
        descr = item.get_description('en')
        assert len(descr) > 3

        assert "Terra" in item.get_aliases()
        assert "planet" in item.get_description()

        assert item.get_label("es") == "Tierra"

        # set_description on already existing description
        item.set_description(descr)
        item.set_description("fghjkl")
        item.set_description("fghjkltest", lang='en', if_exists='KEEP')
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
        # set_description on empty desription
        item.set_description("")
        item.set_description("zaehjgreytret", lang='en', if_exists='KEEP')
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'zaehjgreytret'}

        item.set_label("Earth")
        item.set_label("xfgfdsg")
        item.set_label("xfgfdsgtest", lang='en', if_exists='KEEP')
        assert item.json_representation['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
        item.set_aliases(["fake alias"], if_exists='APPEND')
        assert {'language': 'en', 'value': 'fake alias'} in item.json_representation['aliases']['en']

        item.get_label("ak")
        item.get_description("ak")
        item.get_aliases("ak")
        item.set_label("label", lang='ak')
        item.set_description("d", lang='ak')
        item.set_aliases(["a"], lang='ak', if_exists='APPEND')
        assert item.get_aliases('ak') == ['a']
        item.set_aliases("b", lang='ak')
        assert item.get_aliases('ak') == ['a', 'b']
        item.set_aliases("b", lang='ak', if_exists='REPLACE')
        assert item.get_aliases('ak') == ['b']
        item.set_aliases(["c"], lang='ak', if_exists='REPLACE')
        assert item.get_aliases('ak') == ['c']

    def test_wd_search(self):
        t = wbi_core.FunctionsEngine.get_search_results('rivaroxaban')
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)

    def test_item_generator(self):
        items = ['Q408883', 'P715', 'Q18046452']

        item_instances = wbi_core.FunctionsEngine.generate_item_instances(items=items)

        for qid, item in item_instances:
            self.assertIn(qid, items)

    def test_new_item_creation(self):
        data = [
            wbi_core.String(value='test1', prop_nr='P1'),
            wbi_core.String(value='test2', prop_nr='1'),
            wbi_core.String(value='test3', prop_nr=1),
            wbi_core.Math("xxx", prop_nr="P2"),
            wbi_core.ExternalID("xxx", prop_nr="P3"),
            wbi_core.ItemID("Q123", prop_nr="P4"),
            wbi_core.ItemID("123", prop_nr="P4"),
            wbi_core.ItemID(123, prop_nr="P4"),
            wbi_core.Time(time='-0458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_core.Time(time='458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_core.Time(time='+2021-01-01T15:15:15Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_core.Url("http://www.google.com", prop_nr="P6"),
            wbi_core.MonolingualText(text="xxx", language="fr", prop_nr="P7"),
            wbi_core.Quantity(quantity=-5.04, prop_nr="P8"),
            wbi_core.Quantity(quantity=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P8"),
            wbi_core.CommonsMedia("xxx", prop_nr="P9"),
            wbi_core.GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr="P10"),
            wbi_core.GeoShape("Data:xxx.map", prop_nr="P11"),
            wbi_core.Property("P123", prop_nr="P12"),
            wbi_core.Property("123", prop_nr="P12"),
            wbi_core.Property(123, prop_nr="P12"),
            wbi_core.TabularData("Data:xxx.tab", prop_nr="P13"),
            wbi_core.MusicalNotation("\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P14"),
            wbi_core.Lexeme("L123", prop_nr="P15"),
            wbi_core.Lexeme("123", prop_nr="P15"),
            wbi_core.Lexeme(123, prop_nr="P15"),
            wbi_core.Form("L123-F123", prop_nr="P16"),
            wbi_core.Sense("L123-S123", prop_nr="P17")
        ]
        core_props = set(["P{}".format(x) for x in range(20)])

        for d in data:
            item = wbi_core.ItemEngine(new_item=True, data=[d], core_props=core_props)
            assert item.get_json_representation()
            item = wbi_core.ItemEngine(new_item=True, data=d, core_props=core_props)
            assert item.get_json_representation()
            item = wbi_core.ItemEngine(new_item=True, data=[d], core_props=set())
            assert item.get_json_representation()
            item = wbi_core.ItemEngine(new_item=True, data=d, core_props=set())
            assert item.get_json_representation()

        item = wbi_core.ItemEngine(new_item=True, data=data, core_props=core_props)
        assert item.get_json_representation()
        item = wbi_core.ItemEngine(new_item=True, data=data, core_props=set())
        assert item.get_json_representation()

    def test_get_property_list(self):
        self.assertTrue(len(self.common_item.get_property_list()))

    def test_count_references(self):
        self.assertTrue(len(self.common_item.count_references(prop_id='P2067')))

    def test_get_reference_properties(self):
        self.assertTrue(len(self.common_item.get_reference_properties(prop_id='P2067')))

    def test_get_qualifier_properties(self):
        print(self.common_item.get_qualifier_properties(prop_id='P170'))
        self.assertTrue(len(self.common_item.get_qualifier_properties(prop_id='P2067')))

    def test_get_linked_by(self):
        self.assertTrue(len(wbi_core.FunctionsEngine.get_linked_by('Q2')))
