import unittest
import sys

from .. import wbi_core

class TestItemCreation(unittest.TestCase):
    def test_new_item_creation(self):
        data = [
            wbi_core.WDString(value='test', prop_nr='P1'),
            wbi_core.WDString(value='test1', prop_nr='P2'),
            wbi_core.WDMath("xxx", prop_nr="P3"),
            wbi_core.WDExternalID("xxx", prop_nr="P4"),
            wbi_core.WDItemID("Q123", prop_nr="P5"),
            wbi_core.WDTime('+%Y-%m-%dT%H:%M:%SZ', "P6"),
            wbi_core.WDUrl("http://www.google.com", "P7"),
            wbi_core.WDMonolingualText("xxx", prop_nr="P8"),
            wbi_core.WDQuantity(5, prop_nr="P9"),
            wbi_core.WDQuantity(5, upper_bound=9, lower_bound=2, prop_nr="P10"),
            wbi_core.WDCommonsMedia("xxx", prop_nr="P11"),
            wbi_core.WDGlobeCoordinate(1.2345, 1.2345, 12, prop_nr="P12"),
            wbi_core.WDGeoShape("Data:xxx.map", prop_nr="P13"),
            wbi_core.WDProperty("P123", "P14"),
            wbi_core.WDTabularData("Data:xxx.tab", prop_nr="P15"),
            wbi_core.WDMusicalNotation("\relative c' { c d e f | g2 g | a4 a a a | g1 |}", prop_nr="P16"),
            wbi_core.WDLexeme("L123", prop_nr="P17"),
            wbi_core.WDForm("L123-F123", prop_nr="P18"),
            wbi_core.WDSense("L123-S123", prop_nr="P19")
        ]
        core_props = set(["P{}".format(x) for x in range(20)])

        for d in data:
            item = wbi_core.WDItemEngine(new_item=True, data=[d], core_props=core_props)
            assert item.get_wd_json_representation()
            item = wbi_core.WDItemEngine(new_item=True, data=[d], core_props=set())
            assert item.get_wd_json_representation()

        item = wbi_core.WDItemEngine(new_item=True, data=data, core_props=core_props)
        assert item.get_wd_json_representation()
        item = wbi_core.WDItemEngine(new_item=True, data=data, core_props=set())
        assert item.get_wd_json_representation()
