from typing import Tuple, NamedTuple

class error(Exception): ...

RLIM_INFINITY = ... # type: int
def getrlimit(resource: int) -> Tuple[int, int]: ...
def setrlimit(resource: int, limits: Tuple[int, int]) -> None: ...

RLIMIT_CORE = ... # type: int
RLIMIT_CPU = ... # type: int
RLIMIT_FSIZE = ... # type: int
RLIMIT_DATA = ... # type: int
RLIMIT_STACK = ... # type: int
RLIMIT_RSS = ... # type: int
RLIMIT_NPROC = ... # type: int
RLIMIT_NOFILE = ... # type: int
RLIMIT_OFILE= ... # type: int
RLIMIT_MEMLOCK = ... # type: int
RLIMIT_VMEM = ... # type: int
RLIMIT_AS = ... # type: int

_RUsage = NamedTuple('_RUsage', [('ru_utime', float), ('ru_stime', float), ('ru_maxrss', int),
                                 ('ru_ixrss', int), ('ru_idrss', int), ('ru_isrss', int),
                                 ('ru_minflt', int), ('ru_majflt', int), ('ru_nswap', int),
                                 ('ru_inblock', int), ('ru_oublock', int), ('ru_msgsnd', int),
                                 ('ru_msgrcv', int), ('ru_nsignals', int), ('ru_nvcsw', int),
                                 ('ru_nivcsw', int)])
def getrusage(who: int) -> _RUsage: ...
def getpagesize() -> int: ...

RUSAGE_SELF = ... # type: int
RUSAGE_CHILDREN = ... # type: int
RUSAGE_BOTH = ... # type: int
