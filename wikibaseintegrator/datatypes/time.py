import datetime
import re

from wikibaseintegrator.datatypes.basedatatype import BaseDataType
from wikibaseintegrator.wbi_config import config


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

    def __init__(self, time=None, before=0, after=0, precision=11, timezone=0, calendarmodel=None, wikibase_url=None, **kwargs):
        """
        Constructor, calls the superclass BaseDataType

        :param time: Explicit value for point in time, represented as a timestamp resembling ISO 8601
        :type time: str in the format '+%Y-%m-%dT%H:%M:%SZ', e.g. '+2001-12-31T12:01:13Z' or now
        :param prop_nr: The property number for this claim
        :type prop_nr: str with a 'P' prefix followed by digits
        :param before: explicit integer value for how many units after the given time it could be.
                       The unit is given by the precision.
        :type before: int
        :param after: explicit integer value for how many units before the given time it could be.
                      The unit is given by the precision.
        :type after: int
        :param precision: Precision value for dates and time as specified in the Wikibase data model
                          (https://www.wikidata.org/wiki/Special:ListDatatypes#time)
        :type precision: int
        :param timezone: The timezone which applies to the date and time as specified in the Wikibase data model
        :type timezone: int
        :param calendarmodel: The calendar model used for the date. URL to the Wikibase calendar model item or the QID.
        :type calendarmodel: str
        :param snaktype: The snak type, either 'value', 'somevalue' or 'novalue'
        :type snaktype: str
        :param references: List with reference objects
        :type references: A data type with subclass of BaseDataType
        :param qualifiers: List with qualifier objects
        :type qualifiers: A data type with subclass of BaseDataType
        :param rank: rank of a snak with value 'preferred', 'normal' or 'deprecated'
        :type rank: str
        """

        super().__init__(**kwargs)

        calendarmodel = calendarmodel or config['CALENDAR_MODEL_QID']
        wikibase_url = wikibase_url or config['WIKIBASE_URL']

        if calendarmodel.startswith('Q'):
            calendarmodel = wikibase_url + '/entity/' + calendarmodel

        assert isinstance(time, str) or time is None, f"Expected str, found {type(time)} ({time})"

        if time:
            if time == "now":
                time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            if not (time.startswith("+") or time.startswith("-")):
                time = "+" + time
            pattern = re.compile(r'^[+-][0-9]*-(?:1[0-2]|0[0-9])-(?:3[01]|0[0-9]|[12][0-9])T(?:2[0-3]|[01][0-9]):[0-5][0-9]:[0-5][0-9]Z$')
            matches = pattern.match(time)
            if not matches:
                raise ValueError("Time time must be a string in the following format: '+%Y-%m-%dT%H:%M:%SZ'")

            if precision < 0 or precision > 15:
                raise ValueError("Invalid value for time precision, see https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON#time")

            self.mainsnak.datavalue = {
                'value': {
                    'time': time,
                    'before': before,
                    'after': after,
                    'precision': precision,
                    'timezone': timezone,
                    'calendarmodel': calendarmodel
                },
                'type': 'time'
            }

    def get_sparql_value(self):
        return self.mainsnak.datavalue['value']['time']
