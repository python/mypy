# Stubs for os
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.html

from typing import Undefined, Mapping, Dict, List, Any, Tuple, Iterator, overload, Union, AnyStr
from builtins import OSError as error
import os.path as path

# ----- os variables -----

supports_bytes_environ = False  # TODO: True when bytes implemented?

SEEK_SET = 0 # type: int
SEEK_CUR = 1 # type: int
SEEK_END = 2 # type: int

O_RDONLY = 0
O_WRONLY = 0
O_RDWR = 0
O_APPEND = 0
O_CREAT = 0
O_EXCL = 0
O_TRUNC = 0
O_DSYNC = 0    # Unix only
O_RSYNC = 0    # Unix only
O_SYNC = 0     # Unix only
O_NDELAY = 0   # Unix only
O_NONBLOCK = 0 # Unix only
O_NOCTTY = 0   # Unix only
O_SHLOCK = 0   # Unix only
O_EXLOCK = 0   # Unix only
O_BINARY = 0     # Windows only
O_NOINHERIT = 0  # Windows only
O_SHORT_LIVED = 0# Windows only
O_TEMPORARY = 0  # Windows only
O_RANDOM = 0     # Windows only
O_SEQUENTIAL = 0 # Windows only
O_TEXT = 0       # Windows only
O_ASYNC = 0      # Gnu extension if in C library
O_DIRECT = 0     # Gnu extension if in C library
O_DIRECTORY = 0  # Gnu extension if in C library
O_NOFOLLOW = 0   # Gnu extension if in C library
O_NOATIME = 0    # Gnu extension if in C library

curdir = ''
pardir = ''
sep = ''
altsep = ''
extsep = ''
pathsep = ''
defpath = ''
linesep = ''
devnull = ''

F_OK = 0
R_OK = 0
W_OK = 0
X_OK = 0

environ = Undefined(Mapping[str, str])
environb = Undefined(Mapping[bytes, bytes])

confstr_names = Undefined(Dict[str, int])  # Unix only
pathconf_names = Undefined(Dict[str, int]) # Unix only
sysconf_names = Undefined(Dict[str, int])  # Unix only

EX_OK = 0        # Unix only
EX_USAGE = 0     # Unix only
EX_DATAERR = 0   # Unix only
EX_NOINPUT = 0   # Unix only
EX_NOUSER = 0    # Unix only
EX_NOHOST = 0    # Unix only
EX_UNAVAILABLE = 0  # Unix only
EX_SOFTWARE = 0  # Unix only
EX_OSERR = 0     # Unix only
EX_OSFILE = 0    # Unix only
EX_CANTCREAT = 0 # Unix only
EX_IOERR = 0     # Unix only
EX_TEMPFAIL = 0  # Unix only
EX_PROTOCOL = 0  # Unix only
EX_NOPERM = 0    # Unix only
EX_CONFIG = 0    # Unix only
EX_NOTFOUND = 0  # Unix only

P_NOWAIT = 0
P_NOWAITO = 0
P_WAIT = 0
#P_DETACH = 0  # Windows only
#P_OVERLAY = 0  # Windows only

# wait()/waitpid() options
WNOHANG = 0  # Unix only
#WCONTINUED = 0  # some Unix systems
#WUNTRACED = 0  # Unix only

TMP_MAX = 0  # Undocumented, but used by tempfile

# ----- os classes (structures) -----
class stat_result:
    # For backward compatibility, the return value of stat() is also
    # accessible as a tuple of at least 10 integers giving the most important
    # (and portable) members of the stat structure, in the order st_mode,
    # st_ino, st_dev, st_nlink, st_uid, st_gid, st_size, st_atime, st_mtime,
    # st_ctime. More items may be added at the end by some implementations.

    st_mode = 0 # protection bits,
    st_ino = 0 # inode number,
    st_dev = 0 # device,
    st_nlink = 0 # number of hard links,
    st_uid = 0 # user id of owner,
    st_gid = 0 # group id of owner,
    st_size = 0 # size of file, in bytes,
    st_atime = 0.0 # time of most recent access,
    st_mtime = 0.0 # time of most recent content modification,
    st_ctime = 0.0 # platform dependent (time of most recent metadata change
                   # on  Unix, or the time of creation on Windows)

    def __init__(self, tuple) -> None: pass

    # On some Unix systems (such as Linux), the following attributes may also
    # be available:
    st_blocks = 0 # number of blocks allocated for file
    st_blksize = 0 # filesystem blocksize
    st_rdev = 0 # type of device if an inode device
    st_flags = 0 # user defined flags for file

    # On other Unix systems (such as FreeBSD), the following attributes may be
    # available (but may be only filled out if root tries to use them):
    st_gen = 0 # file generation number
    st_birthtime = 0 # time of file creation

    # On Mac OS systems, the following attributes may also be available:
    st_rsize = 0
    st_creator = 0
    st_type = 0

class statvfs_result:  # Unix only
    f_bsize = 0
    f_frsize = 0
    f_blocks = 0
    f_bfree = 0
    f_bavail = 0
    f_files = 0
    f_ffree = 0
    f_favail = 0
    f_flag = 0
    f_namemax = 0

# ----- os function stubs -----
def name() -> str: pass
def fsencode(filename: str) -> bytes: pass
def fsdecode(filename: bytes) -> str: pass
def get_exec_path(env=None) -> List[str] : pass
# NOTE: get_exec_path(): returns List[bytes] when env not None
def ctermid() -> str: pass  # Unix only
def getegid() -> int: pass  # Unix only
def geteuid() -> int: pass  # Unix only
def getgid() -> int: pass   # Unix only
def getgroups() -> List[int]: pass  # Unix only, behaves differently on Mac
def initgroups(username: str, gid: int) -> None: pass  # Unix only
def getlogin() -> str: pass
def getpgid(pid: int) -> int: pass  # Unix only
def getpgrp() -> int: pass  # Unix only
def getpid() -> int: pass
def getppid() -> int: pass
def getresuid() -> Tuple[int, int, int]: pass  # Unix only
def getresgid() -> Tuple[int, int, int]: pass  # Unix only
def getuid() -> int: pass  # Unix only
def getenv(key: str, default: str = None) -> str: pass
def getenvb(key: bytes, default: bytes = None) -> bytes: pass
# TODO mixed str/bytes putenv arguments
def putenv(key: AnyStr, value: AnyStr) -> None: pass
def setegid(egid: int) -> None: pass  # Unix only
def seteuid(euid: int) -> None: pass  # Unix only
def setgid(gid: int) -> None: pass  # Unix only
def setgroups(groups: List[int]) -> None: pass  # Unix only
def setpgrp() -> int: pass  # Unix only
def setpgid(pid: int, pgrp: int) -> int: pass  # Unix only
def setregid(rgid: int, egid: int) -> None: pass  # Unix only
def setresgid(rgid: int, egid: int, sgid: int) -> None: pass  # Unix only
def setresuid(ruid: int, euid: int, suid: int) -> None: pass  # Unix only
def setreuid(ruid: int, euid: int) -> None: pass  # Unix only
def getsid(pid: int) -> int: pass  # Unix only
def setsid() -> int: pass  # Unix only
def setuid(uid) -> None: pass  # Unix only
def strerror(code: int) -> str: pass
def umask(mask: int) -> int: pass
def uname() -> Tuple[str, str, str, str, str]: pass  # Unix only
def unsetenv(key: AnyStr) -> None: pass
# Return IO or TextIO
def fdopen(fd: int, mode: str = 'r', encoding: str = None, errors: str = None,
           newline: str = None, closefd: bool = True) -> Any: pass
def close(fd: int) -> None: pass
def closerange(fd_low: int, fd_high: int) -> None: pass
def device_encoding(fd: int) -> str: pass # May return None
def dup(fd: int) -> int: pass
def dup2(fd: int, fd2: int) -> None: pass
def fchmod(fd: int, intmode) -> None: pass  # Unix only
def fchown(fd: int, uid: int, gid: int) -> None: pass  # Unix only
def fdatasync(fd: int) -> None: pass  # Unix only, not Mac
def fpathconf(fd: int, name: str) -> int: pass  # Unix only
def fstat(fd: int) -> stat_result: pass
def fstatvfs(fd: int) -> statvfs_result: pass  # Unix only
def fsync(fd: int) -> None: pass
def ftruncate(fd: int, length: int) -> None: pass  # Unix only
def isatty(fd: int) -> bool: pass  # Unix only
def lseek(fd: int, pos: int, how: int) -> int: pass
def open(file: AnyStr, flags: int, mode: int = 0o777) -> int: pass
def openpty() -> Tuple[int, int]: pass  # some flavors of Unix
def pipe() -> Tuple[int, int]: pass
def read(fd: int, n: int) -> bytes: pass
def tcgetpgrp(fd: int) -> int: pass  # Unix only
def tcsetpgrp(fd: int, pg: int) -> None: pass  # Unix only
def ttyname(fd: int) -> str: pass  # Unix only
def write(fd: int, string: bytes) -> int: pass
def access(path: AnyStr, mode: int) -> bool: pass
def chdir(path: AnyStr) -> None: pass
def fchdir(fd: int) -> None: pass
def getcwd() -> str: pass
def getcwdb() -> bytes: pass
def chflags(path: str, flags: int) -> None: pass  # Unix only
def chroot(path: str) -> None: pass  # Unix only
def chmod(path: AnyStr, mode: int) -> None: pass
def chown(path: AnyStr, uid: int, gid: int) -> None: pass  # Unix only
def lchflags(path: str, flags: int) -> None: pass  # Unix only
def lchmod(path: str, mode: int) -> None: pass  # Unix only
def lchown(path: str, uid: int, gid: int) -> None: pass  # Unix only
def link(src: AnyStr, link_name: AnyStr) -> None: pass

@overload
def listdir(path: str = '.') -> List[str]: pass
@overload
def listdir(path: bytes) -> List[bytes]: pass

def lstat(path: AnyStr) -> stat_result: pass
def mkfifo(path, mode: int=0o666) -> None: pass  # Unix only
def mknod(filename: AnyStr, mode: int = 0o600, device: int = 0) -> None: pass
def major(device: int) -> int: pass
def minor(device: int) -> int: pass
def makedev(major: int, minor: int) -> int: pass
def mkdir(path: AnyStr, mode: int = 0o777) -> None: pass
def makedirs(path: AnyStr, mode: int = 0o777,
             exist_ok: bool = False) -> None: pass
def pathconf(path: str, name: str) -> int: pass  # Unix only
def readlink(path: AnyStr) -> AnyStr: pass
def remove(path: AnyStr) -> None: pass
def removedirs(path: AnyStr) -> None: pass
def rename(src: AnyStr, dst: AnyStr) -> None: pass
def renames(old: AnyStr, new: AnyStr) -> None: pass
def rmdir(path: AnyStr) -> None: pass
def stat(path: AnyStr) -> stat_result: pass
def stat_float_times(newvalue: Union[bool, None] = None) -> bool: pass
def statvfs(path: str) -> statvfs_result: pass # Unix only
def symlink(source: AnyStr, link_name: AnyStr,
            target_is_directory: bool = False) -> None:
    pass  # final argument in Windows only
def unlink(path: AnyStr) -> None: pass
def utime(path: AnyStr, times: Union[Tuple[int, int], Tuple[float, float]] = None) -> None: pass

# TODO onerror: function from OSError to void
def walk(top: AnyStr, topdown: bool = True, onerror: Any = None,
         followlinks: bool = False) -> Iterator[Tuple[AnyStr, List[AnyStr],
                                                      List[AnyStr]]]: pass
# walk(): "By default errors from the os.listdir() call are ignored.  If
# optional arg 'onerror' is specified, it should be a function; it
# will be called with one argument, an os.error instance.  It can
# report the error to continue with the walk, or raise the exception
# to abort the walk.  Note that the filename is available as the
# filename attribute of the exception object."

def abort() -> 'None': pass
def execl(path: AnyStr, arg0: AnyStr, *args: AnyStr) -> None: pass
def execle(path: AnyStr, arg0: AnyStr,
           *args: Any) -> None: pass # Imprecise signature
def execlp(path: AnyStr, arg0: AnyStr, *args: AnyStr) -> None: pass
def execlpe(path: AnyStr, arg0: AnyStr,
            *args: Any) -> None: pass # Imprecise signature
def execv(path: AnyStr, args: List[AnyStr]) -> None: pass
def execve(path: AnyStr, args: List[AnyStr], env: Mapping[AnyStr, AnyStr]) -> None: pass
def execvp(file: AnyStr, args: List[AnyStr]) -> None: pass
def execvpe(file: AnyStr, args: List[AnyStr],
            env: Mapping[str, str]) -> None: pass
def _exit(n: int) -> None: pass
def fork() -> int: pass  # Unix only
def forkpty() -> Tuple[int, int]: pass  # some flavors of Unix
def kill(pid: int, sig: int) -> None: pass
def killpg(pgid: int, sig: int) -> None: pass  # Unix only
def nice(increment: int) -> int: pass  # Unix only
def plock(op: int) -> None: pass  # Unix only ???op is int?

from io import TextIOWrapper as _TextIOWrapper
class popen(_TextIOWrapper):
    # TODO 'b' modes or bytes command not accepted?
    def __init__(self, command: str, mode: str = 'r',
                 bufsize: int = -1) -> None: pass
    def close(self) -> Any: pass # may return int

def spawnl(mode: int, path: AnyStr, arg0: AnyStr, *args: AnyStr) -> int: pass
def spawnle(mode: int, path: AnyStr, arg0: AnyStr,
            *args: Any) -> int: pass # Imprecise sig
def spawnlp(mode: int, file: AnyStr, arg0: AnyStr,
            *args: AnyStr) -> int: pass  # Unix only TODO
def spawnlpe(mode: int, file: AnyStr, arg0: AnyStr, *args: Any) -> int:
    pass # Imprecise signature; Unix only TODO
def spawnv(mode: int, path: AnyStr, args: List[AnyStr]) -> int: pass
def spawnve(mode: int, path: AnyStr, args: List[AnyStr],
            env: Mapping[str, str]) -> int: pass
def spawnvp(mode: int, file: AnyStr, args: List[AnyStr]) -> int: pass  # Unix only
def spawnvpe(mode: int, file: AnyStr, args: List[AnyStr],
             env: Mapping[str, str]) -> int:
    pass  # Unix only
def startfile(path: str, operation: Union[str, None] = None) -> None: pass  # Windows only
def system(command: AnyStr) -> int: pass
def times() -> Tuple[float, float, float, float, float]: pass
def wait() -> Tuple[int, int]: pass  # Unix only
def waitpid(pid: int, options: int) -> Tuple[int, int]: pass
def wait3(options: Union[int, None] = None) -> Tuple[int, int, Any]: pass  # Unix only
def wait4(pid: int, options: int) -> Tuple[int, int, Any]:
    pass  # Unix only
def WCOREDUMP(status: int) -> bool: pass  # Unix only
def WIFCONTINUED(status: int) -> bool: pass  # Unix only
def WIFSTOPPED(status: int) -> bool: pass  # Unix only
def WIFSIGNALED(status: int) -> bool: pass  # Unix only
def WIFEXITED(status: int) -> bool: pass  # Unix only
def WEXITSTATUS(status: int) -> bool: pass  # Unix only
def WSTOPSIG(status: int) -> bool: pass  # Unix only
def WTERMSIG(status: int) -> bool: pass  # Unix only
def confstr(name: str) -> str: pass  # Unix only
def getloadavg() -> Tuple[float, float, float]: pass  # Unix only
def sysconf(name: str) -> int: pass  # Unix only
def urandom(n: int) -> bytes: pass
