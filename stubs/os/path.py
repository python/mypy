# Stubs for os.path
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.path.html

# ----- os.path variables -----
bool supports_unicode_filenames

# ----- os.path function stubs -----
str abspath(str path): pass
str basename(path): pass
str commonprefix(str[] list): pass
str dirname(str path): pass
bool exists(str path): pass
bool lexists(str path): pass
str expanduser(str path): pass
str expandvars(str path): pass
int getatime(str path):  # returns float if os.stat_float_times() returns True
    pass
int getmtime(str path):  # returns float if os.stat_float_times() returns True
    pass
int getctime(str path):  # returns float if os.stat_float_times() returns True
    pass
int getsize(str path): pass
bool isabs(str path): pass
bool isfile(str path): pass
bool isdir(str path): pass
bool islink(str path): pass
bool ismount(str path): pass
str join(str path, str *paths): pass
str normcase(str path): pass
str normpath(str path): pass
str realpath(str path): pass
str relpath(str path, str start=None): pass
bool samefile(str path1, str path2): pass
bool sameopenfile(IO fp1, IO fp2): pass
bool sameopenfile(TextIO fp1, TextIO fp2): pass
#bool samestat(stat_result stat1, stat_result stat2): pass  # Unix only
tuple<str, str> split(str path): pass
tuple<str, str> splitdrive(str path): pass
tuple<str, str> splitext(str path): pass
#tuple<str, str> splitunc(str path): pass  # Windows only, deprecated
