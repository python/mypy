# Stubs for time
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/time.html#module-time
# see: http://nullege.com/codes/search?cq=time

# ----- variables and constants -----
bool accept2dyear
int altzone
int daylight
int timezone
tuple<str, str> tzname


# ----- classes/methods -----
class struct_time():
    # this is supposed to be a namedtuple object 
    # namedtuple is not yet implemented (see file: mypy/stubs/collections.py)
    # see: http://docs.python.org/3.2/library/time.html#time.struct_time
    # see: http://nullege.com/codes/search/time.struct_time
    # TODO: namedtuple() object problem
    #namedtuple __init__(self, int, int, int, int, int, int, int, int, int): pass
    #int tm_year
    #int tm_mon
    #int tm_mday
    #int tm_hour
    #int tm_min
    #int tm_sec
    #int tm_wday
    #int tm_yday
    #int tm_isdst
    pass


# ----- functions -----
str asctime(): pass  # return current time
str asctime(struct_time t): pass
str asctime(tuple<str, int> t): pass
float clock(): pass
str ctime(): pass  # return current time
str ctime(float secs): pass
struct_time gmtime(): pass  # return current time
struct_time gmtime(float secs): pass
struct_time localtime(): pass  # return current time
struct_time localtime(float secs): pass
float mktime(struct_time t): pass
void sleep(float secs): pass
void sleep(int secs): pass
str strftime(str format): pass  # return current time
str strftime(str format, struct_time t]): pass
str strftime(str format, tuple<str, int> t): pass
struct_time strptime(str string, str format="%a %b %d %H:%M:%S %Y"): pass
float time(): pass
void tzset(): pass  # Unix only

