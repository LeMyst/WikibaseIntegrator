from __future__ import annotations

import datetime
import re
from functools import total_ordering
from typing import Any, Self

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_enums import WikibaseDatatype, WikibaseSnakType, WikibaseTimePrecision

#: The calendar models known by Wikibase, as found in the ``calendarmodel`` of a time value.
GREGORIAN_CALENDAR = 'http://www.wikidata.org/entity/Q1985727'
JULIAN_CALENDAR = 'http://www.wikidata.org/entity/Q1985786'

# The years of the Julian dates that the RDF export of Wikibase converts to the Gregorian calendar (the range of the
# calendar functions of PHP): the other Julian dates are exported as Gregorian dates
_JULIAN_CONVERSION_YEARS = range(-4713, 1465073)

_TIMESTAMP = re.compile(r'^([+-]?)([0-9]+)-([0-9]{2})-([0-9]{2})T(.*)$')


def _julian_to_day_number(year: int, month: int, day: int) -> int:
    """The Julian day number of a date of the Julian calendar. The year is astronomical: 0 is 1 BCE, -1 is 2 BCE."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def _gregorian_to_day_number(year: int, month: int, day: int) -> int:
    """The Julian day number of a date of the proleptic Gregorian calendar, with an astronomical year."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _day_number_to_gregorian(day_number: int) -> tuple[int, int, int]:
    """The date of the proleptic Gregorian calendar of a Julian day number, as (astronomical year, month, day)."""
    a = day_number + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return 100 * b + d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def _day_number_to_julian(day_number: int) -> tuple[int, int, int]:
    """The date of the Julian calendar of a Julian day number, as (astronomical year, month, day)."""
    c = day_number + 32082
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def _days_in_month(year: int, month: int) -> int:
    """The number of days of a month of the proleptic Gregorian calendar, with an astronomical year."""
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _format_timestamp(year: int, month: int, day: int, rest: str) -> str:
    return f"{'-' if year < 0 else '+'}{abs(year):04d}-{month:02d}-{day:02d}T{rest}"


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

        if time is not None and not isinstance(time, str):
            raise TypeError(f"Expected str, found {type(time)} ({time})")

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
                    raise ValueError(f"Time value ({time}) must be a string in the following format: '+%Y-%m-%dT00:00:00Z'. "
                                     "Check whether the time value format is consistent with the introduced precision.")

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
    def sparql_time(time: str, precision: int | None = None, calendarmodel: str | None = None) -> str:
        """
        Return the timestamp in the form the Wikibase RDF export stores it, an ``xsd:dateTime`` in the proleptic
        Gregorian calendar:

        - the month and the day are set to 01 when they are unknown ('00') or below the precision:
          '+1987-00-00T00:00:00Z' and '+1987-05-17T00:00:00Z' with a year precision both become '+1987-01-01T00:00:00Z';
        - a day beyond the end of the month is set to the last day of the month;
        - with a year precision or finer, the BCE years are numbered like in XSD 1.1, where the year 0 is 1 BCE:
          '-0044-03-15T00:00:00Z' (44 BCE) becomes '-0043-03-15T00:00:00Z';
        - with a day precision or finer, a date of the Julian calendar is converted to the Gregorian calendar:
          '+1500-03-01T00:00:00Z' becomes '+1500-03-11T00:00:00Z'.

        :param time: A timestamp, as found in the JSON representation.
        :param precision: The precision of the timestamp, the day precision if not given.
        :param calendarmodel: The calendar model of the timestamp (an URI), the Gregorian calendar if not given.
        :return: The normalized timestamp, or the timestamp unchanged if it isn't one Wikibase can export as an
            ``xsd:dateTime`` (e.g. the year 0).
        """
        matches = _TIMESTAMP.match(time)
        if not matches or int(matches.group(2)) == 0:
            return time

        sign, digits, month_digits, day_digits, rest = matches.groups()
        precision = WikibaseTimePrecision.DAY.value if precision is None else int(precision)
        year = -int(digits) if sign == '-' else int(digits)
        # The year 0 of the astronomical numbering is 1 BCE, like in XSD 1.1
        astronomical_year = year + 1 if year < 0 else year
        month = min(max(int(month_digits), 1), 12)
        day = max(int(day_digits), 1)

        if calendarmodel == JULIAN_CALENDAR and precision >= WikibaseTimePrecision.DAY.value and year in _JULIAN_CONVERSION_YEARS:
            day_number = _julian_to_day_number(astronomical_year, month, day)
            if day_number > 0:
                return _format_timestamp(*_day_number_to_gregorian(day_number), rest)

        if precision <= WikibaseTimePrecision.YEAR.value:
            month = day = 1
        elif precision == WikibaseTimePrecision.MONTH.value:
            day = 1
        # Like Wikibase, the length of the months of the years before 4713 BCE is the one of 4713 BCE
        day = min(day, _days_in_month(max(astronomical_year, -4712), month))

        # Below the year precision, the year isn't renumbered
        return _format_timestamp(astronomical_year if precision >= WikibaseTimePrecision.YEAR.value else year, month, day, rest)

    @staticmethod
    def time_from_sparql(time: str, precision: int | None = None, calendarmodel: str | None = None) -> str:
        """
        Return the timestamp of the JSON representation of an ``xsd:dateTime`` of the Wikibase RDF export, knowing the
        precision and the calendar model of the value (on the value node of the statement). This reverses
        :meth:`sparql_time`, except for what it loses: an unknown month or day ('00') comes back as '01'.

        :param time: A timestamp of the RDF export, e.g. '-0043-03-15T00:00:00Z'.
        :param precision: The precision of the value, the day precision if not given.
        :param calendarmodel: The calendar model of the value (an URI), the Gregorian calendar if not given.
        :return: The timestamp of the JSON representation, e.g. '-0044-03-15T00:00:00Z', or the timestamp unchanged if
            it isn't one.
        """
        matches = _TIMESTAMP.match(time)
        if not matches:
            return time

        sign, digits, month_digits, day_digits, rest = matches.groups()
        precision = WikibaseTimePrecision.DAY.value if precision is None else int(precision)
        year = -int(digits) if sign == '-' else int(digits)
        month, day = int(month_digits), int(day_digits)

        if precision < WikibaseTimePrecision.YEAR.value:
            return _format_timestamp(year, month, day, rest)

        if calendarmodel == JULIAN_CALENDAR and precision >= WikibaseTimePrecision.DAY.value:
            julian_year, julian_month, julian_day = _day_number_to_julian(_gregorian_to_day_number(year, month, day))
            julian = _format_timestamp(julian_year if julian_year > 0 else julian_year - 1, julian_month, julian_day, rest)
            # Out of the range of the conversion, the RDF export kept the Julian date as a Gregorian one
            if Time.sparql_time(julian, precision, calendarmodel) == _format_timestamp(year, month, day, rest):
                return julian

        return _format_timestamp(year if year > 0 else year - 1, month, day, rest)

    def get_sparql_value(self, **kwargs: Any) -> str:
        value = self.mainsnak.datavalue['value']
        return '"' + self.sparql_time(value['time'], value.get('precision'), value.get('calendarmodel')) + '"^^xsd:dateTime'

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

        # The simple value holds neither the precision nor the calendar model: it is read as a day of the proleptic
        # Gregorian calendar, the calendar of xsd:dateTime. The years of the RDF export are numbered like in XSD 1.1.
        self.set_value(time=self.time_from_sparql(value), calendarmodel=GREGORIAN_CALENDAR)

        return self
