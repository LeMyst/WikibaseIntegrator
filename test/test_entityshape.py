from unittest import TestCase

from entityshape import EntityShape

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_helpers import execute_sparql_query

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_item.py)'
wbi = WikibaseIntegrator()
class TestEntityShape(TestCase):
    def test_validate_one_item(self):
        item = wbi.item.get("Q96620548")
        #item.validate(eid="E1", lang="en")
        e = EntityShape(qid=item.id, eid="E376", lang="en")
        result = e.get_result()
        assert result.is_valid is False
        assert result.required_properties_that_are_missing == ["P137"]

    def test_validate_all_campsite_shelter_items(self):
        # This query was build in a few seconds using https://query.wikidata.org/querybuilder/?uselang=en :)
        results = execute_sparql_query("""
        SELECT DISTINCT ?item ?itemLabel WHERE {
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE]". }
          {
            SELECT DISTINCT ?item WHERE {
              ?item p:P31 ?statement0.
              ?statement0 (ps:P31/(wdt:P279*)) wd:Q96620652.
            }
            LIMIT 100
          }
        }
        """)
        bindings = results["results"]["bindings"]
        print(f"Found {len(bindings)} results")
        count = 1
        for result in bindings:
            qid = result["itemLabel"]["value"]
            print(f"Working on: {qid}")
            #print(result)
            item = wbi.item.get(qid)
            e = EntityShape(qid=item.id, eid="E376", lang="en")
            result = e.get_result()
            # Ignore the invalid shelters missing an operator P137
            if result.is_valid is False and result.required_properties_that_are_missing == {"P137"}:
                print("Skipping campsite only missing and operator")
            elif result.is_valid is True:
                print("Skipping valid campsite - they are boring!")
            else:
                print(f"is_valid: {result.is_valid}, required_properties_that_are_missing:{result.required_properties_that_are_missing}, statements_with_property_that_is_not_allowed:{result.statements_with_property_that_is_not_allowed}, properties_with_too_many_statements:{result.properties_with_too_many_statements}, see {item.get_entity_url()}")
            # assert result.is_valid is False
            # assert result.required_properties_that_are_missing == ["P137"]
