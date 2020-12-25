import unittest

from wikibaseintegrator import wbi_core


class TestItemCreation(unittest.TestCase):
    def test_new_item_creation(self):
        data = [
            wbi_core.String(value='test1', prop_nr='P1'),
            wbi_core.String(value='test2', prop_nr='1'),
            wbi_core.String(value='test3', prop_nr='P2'),
            wbi_core.String(value='test4', prop_nr=2),
            wbi_core.Math("xxx", prop_nr="P3"),
            wbi_core.ExternalID("xxx", prop_nr="P4"),
            wbi_core.ItemID("Q123", prop_nr="P5"),
            wbi_core.ItemID("123", prop_nr="P5"),
            wbi_core.ItemID(123, prop_nr="P5"),
            wbi_core.Time(time='+%Y-%m-%dT%H:%M:%SZ', before=1, after=2, precision=3, timezone=4, prop_nr="P6"),
            wbi_core.Url("http://www.google.com", prop_nr="P7"),
            wbi_core.MonolingualText(text="xxx", language="fr", prop_nr="P8"),
            wbi_core.Quantity(quantity=-5.04, prop_nr="P9"),
            wbi_core.Quantity(quantity=5.06, upper_bound=9.99, lower_bound=-2.22, unit="Q11573", prop_nr="P10"),
            wbi_core.CommonsMedia("xxx", prop_nr="P11"),
            wbi_core.GlobeCoordinate(latitude=1.2345, longitude=-1.2345, precision=12, prop_nr="P12"),
            wbi_core.GeoShape("Data:xxx.map", prop_nr="P13"),
            wbi_core.Property("P123", prop_nr="P14"),
            wbi_core.Property("123", prop_nr="P14"),
            wbi_core.Property(123, prop_nr="P14"),
            wbi_core.TabularData("Data:xxx.tab", prop_nr="P15"),
            wbi_core.MusicalNotation("\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P16"),
            wbi_core.Lexeme("L123", prop_nr="P17"),
            wbi_core.Lexeme("123", prop_nr="P17"),
            wbi_core.Lexeme(123, prop_nr="P17"),
            wbi_core.Form("L123-F123", prop_nr="P18"),
            wbi_core.Sense("L123-S123", prop_nr="P19"),
            wbi_core.LocalMedia("DemoCat 2.png", prop_nr="P20")
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
