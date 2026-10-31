from __future__ import annotations

import datetime
import re
from functools import total_ordering
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType, WikibaseTimePrecision


@total_ordering
class Time(BaseDataType):
    """
    Implements the Wikibase data type with date and time values
    """
    DTYPE = WikibaseDatatype.TIME
    PTYPE = 'http://wikiba.se/ontology#Time'
    sparql_query = '''
        SELECT * WHERE {{
          ?item_id <{wb_url}/prop/{pid}> ?s .
          ?s <{wb_url}/prop/statement/{pid}> '{value}'^^xsd:dateTime .
        }}
    '''

    def __init__(self, time: str | None = None, before: int = 0, after: int = 0, precision: int | WikibaseTimePrecision | None = None, timezone: int = 0,
                 calendarmodel: str | None = None, wikibase_url: str | None = None, **kwargs: Any) -> None:
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

    # The keyword arguments of this public method are named after the parts of the value, not 'value' like in BaseDataType
    # pylint: disable-next=arguments-renamed
    def set_value(self, time: str | None = None, before: int = 0, after: int = 0, precision: int | WikibaseTimePrecision | None = None, timezone: int = 0,
                  calendarmodel: str | None = None, wikibase_url: str | None = None) -> None:
        calendarmodel = calendarmodel or str(config['CALENDAR_MODEL_QID'])
        wikibase_url = wikibase_url or str(config['WIKIBASE_URL'])

        if calendarmodel.startswith('Q'):
            calendarmodel = wikibase_url + '/entity/' + calendarmodel

        assert isinstance(time, str) or time is None, f"Expected str, found {type(time)} ({time})"

        if time:
            if time == "now":
                time = datetime.datetime.now(datetime.UTC).strftime("+%Y-%m-%dT00:00:00Z")

            if not (time.startswith("+") or time.startswith("-")):
                time = "+" + time

            # Pattern with precision lower than day supported
            # pattern = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])T(?:2[0-3]|[01][0-9]):[0-5][0-9]:[0-5][0-9]Z$')

            pattern_day = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])T00:00:00Z$')
            pattern_month = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[1-9])-(?:3[01]|0[0-9]|[12][0-9])T00:00:00Z$')
            pattern_year = re.compile(r'^[+-][0-9]{1,16}-(?:1[0-2]|0[0-9])-(?:3[01]|0[0-9]|[12][0-9])T00:00:00Z$')
            # 'is None': the BILLION_YEARS precision is 0
            if precision is None:
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

                if not isinstance(precision, WikibaseTimePrecision):
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

    @staticmethod
    def sparql_time(time: str, precision: int | None = None) -> str:
        """
        Return the timestamp in the form the Wikibase RDF export stores it: the month and the day are set to 01 when
        they are unknown ('00') or below the precision. '+1987-00-00T00:00:00Z' and '+1987-05-17T00:00:00Z' with a year
        precision both become '+1987-01-01T00:00:00Z'.

        :param time: A timestamp, as found in the JSON representation.
        :param precision: The precision of the timestamp.
        :return: The normalized timestamp.
        """
        matches = re.match(r'^([+-]?[0-9]+)-([0-9]{2})-([0-9]{2})(T.*)$', time)
        if not matches:
            return time

        year, month, day, rest = matches.groups()
        if month == '00' or (precision is not None and precision < WikibaseTimePrecision.MONTH.value):
            month = '01'
        if day == '00' or (precision is not None and precision < WikibaseTimePrecision.DAY.value):
            day = '01'

        return f'{year}-{month}-{day}{rest}'

    def get_sparql_value(self, **kwargs: Any) -> str:
        value = self.mainsnak.datavalue['value']
        return '"' + self.sparql_time(value['time'], value.get('precision')) + '"^^xsd:dateTime'

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

    def __lt__(self, other: Time) -> bool:
        return self._time_parts() < other._time_parts()

    def from_sparql_value(self, sparql_value: dict) -> Self:
        """
        Parse data returned by a SPARQL endpoint and set the value to the object

        :param sparql_value: A SPARQL value composed of type and value
        :return:
        """
        if self._is_unknown_value(sparql_value):
            self.mainsnak.snaktype = WikibaseSnakType.UNKNOWN_VALUE
            return self

        datatype = sparql_value['datatype']
        type = sparql_value['type']
        value = sparql_value['value']

        if datatype != 'http://www.w3.org/2001/XMLSchema#dateTime':
            raise ValueError('Wrong SPARQL datatype')

        if type != 'literal':
            raise ValueError('Wrong SPARQL type')

        self.set_value(time=value)

        return self
