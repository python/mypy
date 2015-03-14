# Stubs for datetime

# NOTE: These are incomplete!

from typing import Optional, SupportsAbs, Tuple, Undefined, Union, overload

MINYEAR = 0
MAXYEAR = 0

class tzinfo:
    def tzname(self, dt: Optional[datetime]) -> str: pass
    def utcoffset(self, dt: Optional[datetime]) -> int: pass
    def dst(self, dt: Optional[datetime]) -> int: pass
    def fromutc(self, dt: datetime) -> datetime: pass

class timezone(tzinfo):
    utc = Undefined(tzinfo)
    min = Undefined(tzinfo)
    max = Undefined(tzinfo)

    def __init__(self, offset: timedelta, name: str = '') -> None: pass
    def __hash__(self) -> int: pass

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
    def __hash__(self) -> int: pass
    def weekday(self) -> int: pass
    def isoweekday(self) -> int: pass
    def isocalendar(self) -> Tuple[int, int, int]: pass

class time:
    min = Undefined(time)
    max = Undefined(time)
    resolution = Undefined(timedelta)

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

    def __le__(self, other: time) -> bool: pass
    def __lt__(self, other: time) -> bool: pass
    def __ge__(self, other: time) -> bool: pass
    def __gt__(self, other: time) -> bool: pass
    def __hash__(self) -> int: pass
    def isoformat(self) -> str: pass
    def strftime(self, fmt: str) -> str: pass
    def __format__(self, fmt: str) -> str: pass
    def utcoffset(self) -> Optional[int]: pass
    def tzname(self) -> Optional[str]: pass
    def dst(self) -> Optional[int]: pass
    def replace(self, hour: int = None, minute: int = None, second: int = None,
                microsecond: int = None, tzinfo: Union[_tzinfo, bool] = True) -> time: pass

_date = date
_time = time

class timedelta(SupportsAbs[timedelta]):
    min = Undefined(timedelta)
    max = Undefined(timedelta)
    resolution = Undefined(timedelta)

    def __init__(self, days: int = 0, seconds: int = 0, microseconds: int = 0,
                 milliseconds: int = 0, minutes: int = 0, hours: int = 0,
                 weeks: int = 0) -> None: pass

    @property
    def days(self) -> int: pass
    @property
    def seconds(self) -> int: pass
    @property
    def microseconds(self) -> int: pass

    def total_seconds(self) -> float: pass
    def __add__(self, other: timedelta) -> timedelta: pass
    def __radd__(self, other: timedelta) -> timedelta: pass
    def __sub__(self, other: timedelta) -> timedelta: pass
    def __rsub(self, other: timedelta) -> timedelta: pass
    def __neg__(self) -> timedelta: pass
    def __pos__(self) -> timedelta: pass
    def __abs__(self) -> timedelta: pass
    def __mul__(self, other: float) -> timedelta: pass
    def __rmul__(self, other: float) -> timedelta: pass
    @overload
    def __floordiv__(self, other: timedelta) -> int: pass
    @overload
    def __floordiv__(self, other: int) -> timedelta: pass
    @overload
    def __truediv__(self, other: timedelta) -> float: pass
    @overload
    def __truediv__(self, other: float) -> timedelta: pass
    def __mod__(self, other: timedelta) -> timedelta: pass
    def __divmod__(self, other: timedelta) -> Tuple[int, timedelta]: pass
    def __le__(self, other: timedelta) -> bool: pass
    def __lt__(self, other: timedelta) -> bool: pass
    def __ge__(self, other: timedelta) -> bool: pass
    def __gt__(self, other: timedelta) -> bool: pass
    def __hash__(self) -> int: pass


class datetime:
    # TODO: Is a subclass of date, but this would make some types incompatible.
    min = Undefined(datetime)
    max = Undefined(datetime)
    resolution = Undefined(timedelta)

    def __init__(self, year: int, month: int = None, day: int = None, hour: int = None,
                 minute: int = None, second: int = None, microseconds: int = None,
                 tzinfo: tzinfo = None) -> None: pass

    @property
    def year(self) -> int: pass
    @property
    def month(self) -> int: pass
    @property
    def day(self) -> int: pass
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
    def today(cls) -> datetime: pass
    @classmethod
    def fromordinal(cls, n: int) -> datetime: pass
    @classmethod
    def now(cls, tz: timezone = None) -> datetime: pass
    @classmethod
    def utcnow(cls) -> datetime: pass
    @classmethod
    def combine(cls, date: date, time: time) -> datetime: pass
    def strftime(self, fmt: str) -> str: pass
    def __format__(self, fmt: str) -> str: pass
    def toordinal(self) -> int: pass
    def timetuple(self) -> tuple: pass # TODO return type
    def timestamp(self) -> float: pass
    def utctimetuple(self) -> tuple: pass # TODO return type
    def date(self) -> _date: pass
    def time(self) -> _time: pass
    def timetz(self) -> _time: pass
    def replace(self, year: int = None, month: int = None, day: int = None, hour: int = None,
                minute: int = None, second: int = None, microsecond: int = None, tzinfo:
                Union[_tzinfo, bool] = True) -> datetime: pass
    def astimezone(self, tz: timezone = None) -> datetime: pass
    def ctime(self) -> str: pass
    def isoformat(self, sep: str = 'T') -> str: pass
    @classmethod
    def strptime(cls, date_string: str, format: str) -> datetime: pass
    def utcoffset(self) -> Optional[int]: pass
    def tzname(self) -> Optional[str]: pass
    def dst(self) -> Optional[int]: pass
    def __le__(self, other: datetime) -> bool: pass
    def __lt__(self, other: datetime) -> bool: pass
    def __ge__(self, other: datetime) -> bool: pass
    def __gt__(self, other: datetime) -> bool: pass
    def __add__(self, other: timedelta) -> datetime: pass
    @overload
    def __sub__(self, other: datetime) -> timedelta: pass
    @overload
    def __sub__(self, other: timedelta) -> datetime: pass
    def __hash__(self) -> int: pass
    def weekday(self) -> int: pass
    def isoweekday(self) -> int: pass
    def isocalendar(self) -> Tuple[int, int, int]: pass
