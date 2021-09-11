import unittest

from wikibaseintegrator import wbi_datatype


class TestWbiDataType(unittest.TestCase):
    def test_qualifier(self):
        # Good
        qualifiers = [wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_qualifier=True),
                      wbi_datatype.ItemID(value='Q24784025', prop_nr='P527', is_qualifier=True),
                      wbi_datatype.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_qualifier=True)]
        wbi_datatype.ItemID("Q123", "P123", qualifiers=qualifiers)

        qualifiers = wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_qualifier=True)
        wbi_datatype.ItemID("Q123", "P123", qualifiers=qualifiers)

        # Bad
        qualifiers = wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_qualifier=False)
        with self.assertRaises(ValueError):
            wbi_datatype.ItemID("Q123", "P123", qualifiers=qualifiers)

        bad_qualifiers = ["not a good qualifier",
                          wbi_datatype.ItemID(value='Q24784025', prop_nr='P527', is_qualifier=True),
                          wbi_datatype.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_qualifier=True)]
        with self.assertRaises(ValueError):
            wbi_datatype.ItemID("Q123", "P123", qualifiers=bad_qualifiers)

    def test_references(self):
        # Good
        references = [wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_reference=True),
                      wbi_datatype.ItemID(value='Q24784025', prop_nr='P527', is_reference=True),
                      wbi_datatype.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_reference=True)]
        wbi_datatype.ItemID("Q123", "P123", references=[references])
        wbi_datatype.ItemID("Q123", "P123", references=references)

        references = wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_reference=True)
        wbi_datatype.ItemID("Q123", "P123", references=references)

        # Bad
        references = wbi_datatype.ExternalID(value='P58742', prop_nr='P352', is_reference=False)
        with self.assertRaises(ValueError):
            wbi_datatype.ItemID("Q123", "P123", references=references)

        bad_references = ["not a good reference",
                          wbi_datatype.ItemID(value='Q24784025', prop_nr='P527', is_reference=True),
                          wbi_datatype.Time(time='+2001-12-31T12:01:13Z', prop_nr='P813', is_reference=True)]
        with self.assertRaises(ValueError):
            wbi_datatype.ItemID("Q123", "P123", qualifiers=bad_references)
