# Stubs for time
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/time.html#module-time
# see: http://nullege.com/codes/search?cq=time

from typing import Undefined, Tuple, overload

# ----- variables and constants -----
accept2dyear = False
altzone = 0
daylight = 0
timezone = 0
tzname = Undefined(Tuple[str, str])


# ----- classes/methods -----
class struct_time:
    # this is supposed to be a namedtuple object
    # namedtuple is not yet implemented (see file: mypy/stubs/collections.py)
    # see: http://docs.python.org/3.2/library/time.html#time.struct_time
    # see: http://nullege.com/codes/search/time.struct_time
    # TODO: namedtuple() object problem
    #namedtuple __init__(self, int, int, int, int, int, int, int, int, int):
    #    pass
    tm_year = 0
    tm_mon = 0
    tm_mday = 0
    tm_hour = 0
    tm_min = 0
    tm_sec = 0
    tm_wday = 0
    tm_yday = 0
    tm_isdst = 0


# ----- functions -----
@overload
def asctime() -> str: pass  # return current time
@overload
def asctime(t: struct_time) -> str: pass
@overload
def asctime(t: Tuple[int, int, int, int, int, int, int, int, int]) -> str: pass

def clock() -> float: pass

@overload
def ctime() -> str: pass  # return current time
@overload
def ctime(secs: float) -> str: pass

@overload
def gmtime() -> struct_time: pass  # return current time
@overload
def gmtime(secs: float) -> struct_time: pass

@overload
def localtime() -> struct_time: pass  # return current time
@overload
def localtime(secs: float) -> struct_time: pass

@overload
def mktime(t: struct_time) -> float: pass
@overload
def mktime(t: Tuple[int, int, int, int, int,
                    int, int, int, int]) -> float: pass

@overload
def sleep(secs: int) -> None: pass
@overload
def sleep(secs: float) -> None: pass

@overload
def strftime(format: str) -> str: pass  # return current time
@overload
def strftime(format: str, t: struct_time) -> str: pass
@overload
def strftime(format: str, t: Tuple[int, int, int, int, int,
                                   int, int, int, int]) -> str: pass

def strptime(string: str,
             format: str = "%a %b %d %H:%M:%S %Y") -> struct_time: pass
def time() -> float: pass
def tzset() -> None: pass  # Unix only
