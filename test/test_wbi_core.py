import unittest

from wikibaseintegrator import wbi_core, wbi_functions, wbi_datatype


class TestWbiCore(unittest.TestCase):
    common_item = wbi_core.ItemEngine(item_id="Q2")

    def test_item_engine(self):
        wbi_core.ItemEngine(debug=True)
        wbi_core.ItemEngine(data=None, debug=True)
        wbi_core.ItemEngine(data=wbi_datatype.String(value='test', prop_nr='P1'), debug=True)
        wbi_core.ItemEngine(data=[wbi_datatype.String(value='test', prop_nr='P1')], debug=True)
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
        instance_of_append = wbi_datatype.ItemID(prop_nr='P31', value='Q1234', if_exists='APPEND')
        instance_of_forceappend = wbi_datatype.ItemID(prop_nr='P31', value='Q1234', if_exists='FORCE_APPEND')
        instance_of_replace = wbi_datatype.ItemID(prop_nr='P31', value='Q1234', if_exists='REPLACE')
        instance_of_keep = wbi_datatype.ItemID(prop_nr='P31', value='Q1234', if_exists='KEEP')

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_append, instance_of_append])
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) > 1 and 'Q1234' in claims and claims.count('Q1234') == 1

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_forceappend, instance_of_forceappend])
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) > 1 and 'Q1234' in claims and claims.count('Q1234') == 2

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_replace], debug=True)
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31'] if 'remove' not in x]
        removed_claims = [True for x in item.get_json_representation()['claims']['P31'] if 'remove' in x]
        assert len(claims) == 1 and 'Q1234' in claims and len(removed_claims) == 2 and True in removed_claims

        item = wbi_core.ItemEngine(item_id="Q2", data=[instance_of_keep], debug=True)
        claims = [x['mainsnak']['datavalue']['value']['id'] for x in item.get_json_representation()['claims']['P31']]
        assert len(claims) == 2 and 'Q1234' not in claims

    def test_description(self):
        item = wbi_core.ItemEngine(item_id="Q2")
        descr = item.get_description('en')
        assert len(descr) > 3

        assert "planet" in item.get_description()

        # set_description on already existing description
        item.set_description(descr)
        item.set_description("lorem")
        item.set_description("lorem ipsum", lang='en', if_exists='KEEP')
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'lorem'}
        # set_description on empty desription
        item.set_description("")
        item.set_description("lorem ipsum", lang='en', if_exists='KEEP')
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}

        item.set_description("lorem", lang='fr', if_exists='KEEP')
        item.set_description("lorem ipsum", lang='fr', if_exists='REPLACE')
        item.set_description("lorem", lang='en', if_exists='KEEP')
        assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'lorem ipsum'}
        assert item.json_representation['descriptions']['fr'] == {'language': 'fr', 'value': 'lorem ipsum'}

    def test_label(self):
        item = wbi_core.ItemEngine(item_id="Q2")

        assert item.get_label('en') == "Earth"

        assert "Terra" in item.get_aliases()

        assert item.get_label("es") == "Tierra"

        item.set_label("Earth")
        item.set_label("lorem")
        item.set_label("lorem ipsum", lang='en', if_exists='KEEP')
        assert item.json_representation['labels']['en'] == {'language': 'en', 'value': 'lorem'}
        assert item.json_representation['labels']['fr'] == {'language': 'fr', 'value': 'Terre'}
        item.set_aliases(["fake alias"], if_exists='APPEND')
        assert {'language': 'en', 'value': 'fake alias'} in item.json_representation['aliases']['en']

        item.set_label(label=None, lang='fr')
        item.set_label(label=None, lang='non-exist-key')
        assert 'remove' in item.json_representation['labels']['fr']

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
        t = wbi_functions.search_entities('rivaroxaban')
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)

    def test_item_generator(self):
        items = ['Q408883', 'P715', 'Q18046452']

        item_instances = wbi_functions.generate_item_instances(items=items)

        for qid, item in item_instances:
            self.assertIn(qid, items)

    def test_new_item_creation(self):
        data = [
            wbi_datatype.String(value='test1', prop_nr='P1'),
            wbi_datatype.String(value='test2', prop_nr='1'),
            wbi_datatype.String(value='test3', prop_nr=1),
            wbi_datatype.Math("xxx", prop_nr="P2"),
            wbi_datatype.ExternalID("xxx", prop_nr="P3"),
            wbi_datatype.ItemID("Q123", prop_nr="P4"),
            wbi_datatype.ItemID("123", prop_nr="P4"),
            wbi_datatype.ItemID(123, prop_nr="P4"),
            wbi_datatype.Time(time='-0458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_datatype.Time(time='458-00-00T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_datatype.Time(time='+2021-01-01T15:15:15Z', before=1, after=2, precision=3, timezone=4, prop_nr="P5"),
            wbi_datatype.Url("http://www.wikidata.org", prop_nr="P6"),
            wbi_datatype.Url("https://www.wikidata.org", prop_nr="P6"),
            wbi_datatype.Url("ftp://example.com", prop_nr="P6"),
            wbi_datatype.Url("ssh://user@server/project.git", prop_nr="P6"),
            wbi_datatype.Url("svn+ssh://user@server:8888/path", prop_nr="P6"),
            wbi_datatype.MonolingualText(text="xxx", language="fr", prop_nr="P7"),
            wbi_datatype.Quantity(quantity=-5.04, prop_nr="P8"),
            wbi_datatype.Quantity(quantity=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P8"),
            wbi_datatype.CommonsMedia("xxx", prop_nr="P9"),
            wbi_datatype.GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr="P10"),
            wbi_datatype.GeoShape("Data:xxx.map", prop_nr="P11"),
            wbi_datatype.Property("P123", prop_nr="P12"),
            wbi_datatype.Property("123", prop_nr="P12"),
            wbi_datatype.Property(123, prop_nr="P12"),
            wbi_datatype.TabularData("Data:Taipei+Population.tab", prop_nr="P13"),
            wbi_datatype.MusicalNotation("\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P14"),
            wbi_datatype.Lexeme("L123", prop_nr="P15"),
            wbi_datatype.Lexeme("123", prop_nr="P15"),
            wbi_datatype.Lexeme(123, prop_nr="P15"),
            wbi_datatype.Form("L123-F123", prop_nr="P16"),
            wbi_datatype.Sense("L123-S123", prop_nr="P17"),
            wbi_datatype.LocalMedia("DemoCat 2.png", prop_nr="P18")
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
