# Stubs for time
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/time.html#module-time
# see: http://nullege.com/codes/search?cq=time

from typing import Undefined, Tuple, Union

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
def asctime(t: Union[Tuple[int, int, int, int, int, int, int, int, int],
                     struct_time,
                     None] = None) -> str: pass  # return current time

def clock() -> float: pass

def ctime(secs: Union[float, None] = None) -> str: pass  # return current time

def gmtime(secs: Union[float, None] = None) -> struct_time: pass  # return current time

def localtime(secs: Union[float, None] = None) -> struct_time: pass  # return current time

def mktime(t: Union[Tuple[int, int, int, int, int,
                          int, int, int, int],
                    struct_time]) -> float: pass

def sleep(secs: Union[int, float]) -> None: pass

def strftime(format: str, t: Union[Tuple[int, int, int, int, int,
                                         int, int, int, int],
                                   struct_time,
                                   None] = None) -> str: pass  # return current time

def strptime(string: str,
             format: str = "%a %b %d %H:%M:%S %Y") -> struct_time: pass
def time() -> float: pass
def tzset() -> None: pass  # Unix only
