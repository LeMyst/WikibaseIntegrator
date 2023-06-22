from unittest import TestCase

from entityshape import EntityShape

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'
wbi = WikibaseIntegrator()
class TestEntityShape(TestCase):
    def test_validate_one_item(self):
        item = wbi.item.get("Q1")
        #item.validate(eid="E1", lang="en")
        e = EntityShape(qid=item.id, eid="E1", lang="en")
        result = e.get_result()
        print(result)
        assert result != {}
