# Stubs for datetime

# NOTE: These are incomplete!

from typing import Tuple, Undefined, overload, disjointclass

MINYEAR = 0
MAXYEAR = 0

class tzinfo: pass
class timezone(tzinfo): pass

_tzinfo = tzinfo
_timezone = timezone

class date:
    min = Undefined(date)
    max = Undefined(date)
    resolution = Undefined(timedelta)

    def __init__(self, year: int, month: int = None, day: int = None) -> None: pass

    @classmethod
    def fromtimestamp(cls, t: float) -> date: pass
    @classmethod
    def today(cls) -> date: pass
    @classmethod
    def fromordinal(cls, n: int) -> date: pass

    @property
    def year(self) -> int: pass
    @property
    def month(self) -> int: pass
    @property
    def day(self) -> int: pass

    def ctime(self) -> str: pass
    def strftime(self, fmt: str) -> str: pass
    def __format__(self, fmt: str) -> str: pass
    def isoformat(self) -> str: pass
    def timetuple(self) -> tuple: pass # TODO return type
    def toordinal(self) -> int: pass
    def replace(self, year: int = None, month: int = None, day: int = None) -> date: pass
    def __le__(self, other: date) -> bool: pass
    def __lt__(self, other: date) -> bool: pass
    def __ge__(self, other: date) -> bool: pass
    def __gt__(self, other: date) -> bool: pass
    def __add__(self, other: timedelta) -> date: pass
    @overload
    def __sub__(self, other: timedelta) -> date: pass
    @overload
    def __sub__(self, other: date) -> timedelta: pass
    def weekday(self) -> int: pass
    def isoweekday(self) -> int: pass
    def isocalendar(self) -> Tuple[int, int, int]: pass

class time:
    def __init__(self, hour: int = 0, minute: int = 0, second: int = 0, microsecond: int = 0,
                 tzinfo: tzinfo = None) -> None: pass

    @property
    def hour(self) -> int: pass
    @property
    def minute(self) -> int: pass
    @property
    def second(self) -> int: pass
    @property
    def microsecond(self) -> int: pass
    @property
    def tzinfo(self) -> _tzinfo: pass

_date = date
_time = time

@disjointclass(date)
@disjointclass(datetime)
class timedelta:
    def __init__(self, days: int = 0, seconds: int = 0, microseconds: int = 0,
                 milliseconds: int = 0, minutes: int = 0, hours: int = 0,
                 weeks: int = 0) -> None: pass

    @property
    def days(self) -> int: pass
    @property
    def seconds(self) -> int: pass
    @property
    def microseconds(self) -> int: pass

class datetime:
    min = Undefined(datetime)
    max = Undefined(datetime)
    resolution = Undefined(timedelta)

    def __init__(self, year: int, month: int = None, day: int = None, hour: int = None,
                 minute: int = None, second: int = None, microseconds: int = None,
                 tzinfo: tzinfo = None) -> None: pass

    @property
    def hour(self) -> int: pass
    @property
    def minute(self) -> int: pass
    @property
    def second(self) -> int: pass
    @property
    def microsecond(self) -> int: pass
    @property
    def tzinfo(self) -> _tzinfo: pass

    @classmethod
    def fromtimestamp(cls, t: float, tz: timezone = None) -> datetime: pass
    @classmethod
    def utcfromtimestamp(cls, t: float) -> datetime: pass
    @classmethod
    def now(cls, tz: timezone = None) -> datetime: pass
    @classmethod
    def utcnow(cls) -> datetime: pass
    @classmethod
    def combine(cls, date: date, time: time) -> datetime: pass
    def timetuple(self) -> tuple: pass # TODO return type
    def timestamp(self) -> float: pass
    def utctimetuple(self) -> tuple: pass # TODO return type
    def date(self) -> _date: pass
    def time(self) -> _time: pass
    def timetz(self) -> _time: pass
    def replace(self, year: int = None, month: int = None, day: int = None, hour: int = None,
                minute: int = None, second: int = None, microsecond: int = None, tzinfo:
                _tzinfo = None) -> datetime: pass
    def astimezone(self, tz: timezone = None) -> datetime: pass
    def ctime(self) -> str: pass
    def isoformat(self, sep: str = 'T') -> str: pass
    @classmethod
    def strptime(cls, date_string: str, format: str) -> datetime: pass
    def utcoffset(self) -> int: pass
    def tzname(self) -> str: pass
    def dst(self) -> int: pass
    def __le__(self, other: datetime) -> bool: pass
    def __lt__(self, other: datetime) -> bool: pass
    def __ge__(self, other: datetime) -> bool: pass
    def __gt__(self, other: datetime) -> bool: pass
    def __add__(self, other: timedelta) -> datetime: pass
    @overload
    def __sub__(self, other: datetime) -> timedelta: pass
    @overload
    def __sub__(self, other: timedelta) -> datetime: pass
