# Stubs for the sys module

list<str> argv
str byteorder
str exec_prefix
str executable
str float_repr_style
int hexversion
int maxsize
int maxunicode
list<str> path
str platform
str prefix
str ps1
str ps2
TextIO stdin
TextIO stdout
TextIO stderr
TextIO __stdin__
TextIO __stdout__
TextIO __stderr__
int tracebacklimit
str version
int api_version

# TODO type of traceback
tuple<type, any, any> exc_info(): pass
void exit(any arg=0): pass
str getdefaultencoding(): pass
str getfilesystemencoding(): pass
str intern(str string): pass

# TODO these are not available:
#
# abiflags
# list<str> builtin_module_names
# def call_tracing(func, args): pass
# str copyright
# int dllhandle
# def displayhook(value): pass
# bool dont_write_bytecode
# def excepthook(type, value, traceback): pass
# __displayhook__
# __excepthook__
# flags
# float_info
# getcheckinterval
# getdlopenflags
# getrefcount
# getrecursionlimit
# getsizeof
# getswitchinterval
# _getframe
# getprofile
# gettrace
# getwindowsversion
# hash_info
# int_info
# last_type
# last_value
# last_traceback
# meta_path
# modules
# path_hooks
# path_importer_cache
# setcheckinterval
# setdlopenflags
# setprofile
# setrecursionlimit
# setswitchinterval
# settrace
# version_info
# winver
