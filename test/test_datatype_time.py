import unittest

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Time
from wikibaseintegrator.wbi_config import config as wbi_config

wbi_config['USER_AGENT'] = 'WikibaseIntegrator-pytest/1.0 (test_entity_property.py)'

wbi = WikibaseIntegrator()


class TestDatatypeTime(unittest.TestCase):

    def test_get(self):
        time = Time(time='-2023-12-31T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5')
        assert time.get_year() == -2023
        assert time.get_month() == 12
        assert time.get_day() == 31

        time2 = Time(time='2023-12-31T00:00:00Z', before=1, after=2, precision=3, timezone=4, prop_nr='P5')
        assert time2.get_year() == 2023
        assert time == time
        assert time < time2
        assert time <= time2
        assert time != time2
