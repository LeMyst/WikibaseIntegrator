import pprint
import unittest

from wikibaseintegrator import wbi_core

__author__ = 'Sebastian Burgstaller-Muehlbacher'
__license__ = 'AGPLv3'


class TestItemGenerator(unittest.TestCase):

    def test_item_generator(self):
        items = ['Q408883', 'P715', 'Q18046452']

        login_obj = None
        item_instances = wbi_core.ItemEngine.generate_item_instances(items=items, login=login_obj)

        for qid, item in item_instances:
            print(qid)
            pprint.pprint(item.entity_metadata)
