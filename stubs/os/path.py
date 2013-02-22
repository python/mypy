# Stubs for os.path
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.path.html

# ----- os.path variables -----
bool supports_unicode_filenames

# ----- os.path function stubs -----
str abspath(str path): pass
bytes abspath(bytes path): pass
str basename(str path): pass
bytes basename(bytes path): pass
str commonprefix(str[] list): pass
bytes commonprefix(bytes[] list): pass
str dirname(str path): pass
bytes dirname(bytes path): pass
bool exists(str path): pass
bool exists(bytes path): pass
bool lexists(str path): pass
bool lexists(bytes path): pass
str expanduser(str path): pass
bytes expanduser(bytes path): pass
str expandvars(str path): pass
bytes expandvars(bytes path): pass

# These return float if os.stat_float_times() == True
any getatime(str path): pass
any getatime(bytes path): pass
any getmtime(str path): pass
any getmtime(bytes path): pass
any getctime(str path): pass
any getctime(bytes path): pass

int getsize(str path): pass
int getsize(bytes path): pass
bool isabs(str path): pass
bool isabs(bytes path): pass
bool isfile(str path): pass
bool isfile(bytes path): pass
bool isdir(str path): pass
bool isdir(bytes path): pass
bool islink(str path): pass
bool islink(bytes path): pass
bool ismount(str path): pass
bool ismount(bytes path): pass
str join(str path, str *paths): pass
bytes join(bytes path, bytes *paths): pass
str normcase(str path): pass
bytes normcase(bytes path): pass
str normpath(str path): pass
bytes normpath(bytes path): pass
str realpath(str path): pass
bytes realpath(bytes path): pass
str relpath(str path, str start=None): pass
bytes relpath(bytes path, bytes start=None): pass
bool samefile(str path1, str path2): pass
bool samefile(bytes path1, bytes path2): pass
bool sameopenfile(IO fp1, IO fp2): pass
bool sameopenfile(TextIO fp1, TextIO fp2): pass
#bool samestat(stat_result stat1, stat_result stat2): pass  # Unix only
tuple<str, str> split(str path): pass
tuple<bytes, bytes> split(bytes path): pass
tuple<str, str> splitdrive(str path): pass
tuple<bytes, bytes> splitdrive(bytes path): pass
tuple<str, str> splitext(str path): pass
tuple<bytes, bytes> splitext(bytes path): pass
#tuple<str, str> splitunc(str path): pass  # Windows only, deprecated
