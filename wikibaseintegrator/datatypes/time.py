import datetime
import re
from functools import total_ordering
from typing import Any

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseTimePrecision


@total_ordering
class Time(BaseDataType):
    """
    Implements the Wikibase data type with date and time values
    """
    DTYPE = 'time'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:dateTime .
        }}
    '''

    def __init__(self, time: str | None = None, before: int = 0, after: int = 0, precision: int | WikibaseTimePrecision | None = None, timezone: int = 0,
                 calendarmodel: str | None = None, wikibase_url: str | None = None, **kwargs: Any):
        """
        Constructor, calls the superclass BaseDataType

        :param time: Explicit value for point in time, represented as a timestamp resembling ISO 8601. You can use the keyword 'now' to get the current UTC date.
        :param prop_nr: The property number for this claim
        :param before: explicit integer value for how many units after the given time it could be.
                       The unit is given by the precision.
        :param after: explicit integer value for how many units before the given time it could be.
                      The unit is given by the precision.
        :param precision: Precision value for dates and time as specified in the Wikibase data model
                          (https://www.wikidata.org/wiki/Special:ListDatatypes#time)
        :param timezone: The timezone which applies to the date and time as specified in the Wikibase data model
        :param calendarmodel: The calendar model used for the date. URL to the Wikibase calendar model item or the QID.
        """

        super().__init__(**kwargs)
        self.set_value(time=time, before=before, after=after, precision=precision, timezone=timezone, calendarmodel=calendarmodel, wikibase_url=wikibase_url)

    def set_value(self, time: str | None = None, before: int = 0, after: int = 0, precision: int | WikibaseTimePrecision | None = None, timezone: int = 0,
                  calendarmodel: str | None = None, wikibase_url: str | None = None):
        calendarmodel = calendarmodel or str(config['CALENDAR_MODEL_QID'])
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        if calendarmodel.startswith('Q'):
            calendarmodel = wikibase_url + '/entity/' + calendarmodel

        assert isinstance(time, str) or time is None, f"Expected str, found {type(time)} ({time})"

        if time:
            if time == "now":
                time = datetime.datetime.now(datetime.timezone.utc).strftime("+%Y-%m-%dT00:00:00Z")

            if not (time.startswith("+") or time.startswith("-")):
                time = "+" + time

            # Pattern with precision lower than day supported
            # pattern = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])T(?:2[0-3]|[01][0-9]):[0-5][0-9]:[0-5][0-9]Z$')

            pattern_day = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])T00:00:00Z$')
            pattern_month = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[0-9]|[12][0-9])T00:00:00Z$')
            pattern_year = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[0-9])-(?:3[01]|0[0-9]|[12][0-9])T00:00:00Z$')
            if not precision:
                if pattern_day.match(time):
                    precision = WikibaseTimePrecision.DAY
                elif pattern_month.match(time):
                    precision = WikibaseTimePrecision.MONTH
                elif pattern_year.match(time):
                    precision = WikibaseTimePrecision.YEAR
                else:
                    raise ValueError(f"Time value ({time}) must be a string in the following format: '+%Y-%m-%dT00:00:00Z'.")
            else:
                if isinstance(precision, int):
                    precision = WikibaseTimePrecision(precision)

                if precision not in WikibaseTimePrecision:
                    raise ValueError("Invalid value for time precision, see https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON#time")

                if precision == WikibaseTimePrecision.DAY:
                    pattern = pattern_day
                elif precision == WikibaseTimePrecision.MONTH:
                    pattern = pattern_month
                else:
                    pattern = pattern_year
                matches = pattern.match(time)
                if not matches:
                    raise ValueError(f"Time value ({time}) must be a string in the following format: '+%Y-%m-%dT00:00:00Z'. Check whether the time value format is consistent with the introduced precision.")

            self.mainsnak.datavalue = {
                'value': {
                    'time': time,
                    'before': before,
                    'after': after,
                    'precision': precision.value,
                    'timezone': timezone,
                    'calendarmodel': calendarmodel
                },
                'type': 'time'
            }

    def get_sparql_value(self) -> str:
        return self.mainsnak.datavalue['value']['time']

    def parse_sparql_value(self, value, type='literal', unit='1') -> bool:
        pattern = re.compile(r'^"?([+-]?[0-9]{1,16}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"?(?:\^\^xsd:dateTime)?$')
        matches = pattern.match(value)
        if not matches:
            return False

        try:
            # The RDF value does not carry the precision, set_value() infers it from the timestamp
            self.set_value(time=matches.group(1))
        except ValueError:
            # The precision cannot be inferred (e.g. a timestamp with a time part), set_value() cannot represent it
            return False

        return True

    def _time_parts(self) -> tuple[int, int, int]:
        """
        Split the timestamp into (year, month, day).

        The year can be signed and hold more than 4 digits (up to 16), so it can't be sliced at fixed positions.
        """
        time = self.mainsnak.datavalue['value']['time']
        matches = re.match(r'^([+-]?[0-9]+)-([0-9]{2})-([0-9]{2})T', time)
        if not matches:
            raise ValueError(f"Unable to parse time value '{time}'")
        return int(matches.group(1)), int(matches.group(2)), int(matches.group(3))

    def get_year(self) -> int:
        return self._time_parts()[0]

    def get_month(self) -> int:
        return self._time_parts()[1]

    def get_day(self) -> int:
        return self._time_parts()[2]

    def __lt__(self, other):
        return self._time_parts() < other._time_parts()
