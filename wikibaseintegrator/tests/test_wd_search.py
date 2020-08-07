import unittest

from wikibaseintegrator import wbi_core

__author__ = 'Sebastian Burgstaller-Muehlbacher'
__license__ = 'AGPLv3'


class TestWDSearch(unittest.TestCase):

    def test_wd_search(self):
        t = wbi_core.ItemEngine.get_search_results('rivaroxaban')

        print(t)
        print('Number of results: ', len(t))
        self.assertIsNot(len(t), 0)
