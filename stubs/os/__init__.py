# Stubs for os
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.html

# ----- os variables -----

bool supports_bytes_environ = False  # TODO: True when bytes implemented?

int SEEK_SET = 0
int SEEK_CUR = 1
int SEEK_END = 2

int O_RDONLY
int O_WRONLY
int O_RDWR
int O_APPEND
int O_CREAT
int O_EXCL
int O_TRUNC
#int O_DSYNC  # Unix only
#int O_RSYNC  # Unix only
#int O_SYNC  # Unix only
#int O_NDELAY  # Unix only
#int O_NONBLOCK  # Unix only
#int O_NOCTTY  # Unix only
#int O_SHLOCK  # Unix only
#int O_EXLOCK  # Unix only
#int O_BINARY  # Windows only
#int O_NOINHERIT  # Windows only
#int O_SHORT_LIVED  # Windows only
#int O_TEMPORARY  # Windows only
#int O_RANDOM  # Windows only
#int O_SEQUENTIAL  # Windows only
#int O_TEXT  # Windows only
#int O_ASYNC  # Gnu extension if in C library
#int O_DIRECT  # Gnu extension if in C library
#int O_DIRECTORY  # Gnu extension if in C library
#int O_NOFOLLOW  # Gnu extension if in C library
#int O_NOATIME  # Gnu extension if in C library

str curdir
str pardir
str sep
str altsep
str extsep
str pathsep
str defpath
str linesep
str devnull

int F_OK
int R_OK
int W_OK
int X_OK

Mapping<str, str> environ
Mapping<bytes, bytes> environb

#dict<str, int> confstr_names  # Unix only
#dict<str, int> pathconf_names # Unix only
#dict<str, int> sysconf_names  # Unix only

#int EX_OK  # Unix only
#int EX_USAGE  # Unix only
#int EX_DATAERR  # Unix only
#int EX_NOINPUT  # Unix only
#int EX_NOUSER  # Unix only
#int EX_NOHOST  # Unix only
#int EX_UNAVAILABLE  # Unix only
#int EX_SOFTWARE  # Unix only
#int EX_OSERR  # Unix only
#int EX_OSFILE  # Unix only
#int EX_CANTCREAT  # Unix only
#int EX_IOERR  # Unix only
#int EX_TEMPFAIL  # Unix only
#int EX_PROTOCOL  # Unix only
#int EX_NOPERM  # Unix only
#int EX_CONFIG  # Unix only
#int EX_NOTFOUND  # Unix only

int P_NOWAIT
int P_NOWAITO
int P_WAIT
#int P_DETACH  # Windows only
#int P_OVERLAY  # Windows only

# wait()/waitpid() options
#int WNOHANG  # Unix only
#int WCONTINUED  # some Unix systems
#int WUNTRACED  # Unix only

# ----- os classes (structures) -----
class stat_result:
    # For backward compatibility, the return value of stat() is also 
    # accessible as a tuple of at least 10 integers giving the most important 
    # (and portable) members of the stat structure, in the order st_mode, 
    # st_ino, st_dev, st_nlink, st_uid, st_gid, st_size, st_atime, st_mtime, 
    # st_ctime. More items may be added at the end by some implementations.

    int st_mode # protection bits,
    int st_ino # inode number,
    int st_dev # device,
    int st_nlink # number of hard links,
    int st_uid # user id of owner,
    int st_gid # group id of owner,
    int st_size # size of file, in bytes,
    int st_atime # time of most recent access,
    int st_mtime # time of most recent content modification,
    int st_ctime # platform dependent (time of most recent metadata change on 
                 # Unix, or the time of creation on Windows)

    # On some Unix systems (such as Linux), the following attributes may also 
    # be available:
    #int st_blocks # number of blocks allocated for file
    #int st_blksize # filesystem blocksize
    #int st_rdev # type of device if an inode device
    #int st_flags # user defined flags for file

    # On other Unix systems (such as FreeBSD), the following attributes may be
    # available (but may be only filled out if root tries to use them):
    #int st_gen # file generation number
    #int st_birthtime # time of file creation

    # On Mac OS systems, the following attributes may also be available:
    #int st_rsize
    #int st_creator
    #int st_type

#class statvfs_result:  # Unix only
    #int f_bsize
    #int f_frsize
    #int f_blocks
    #int f_bfree
    #int f_bavail
    #int f_files
    #int f_ffree
    #int f_favail
    #int f_flag 
    #int f_namemax

# ----- os function stubs -----
OSError error(): pass
str name(): pass
bytes fsencode(str filename): pass
str fsdecode(bytes filename): pass
str[] get_exec_path(env=None) : pass
# NOTE: get_exec_path(): returns bytes[] when env not None
#str ctermid(): pass  # Unix only
#int getegid(): pass  # Unix only
#int geteuid(): pass  # Unix only
#int getgid(): pass  # Unix only
#int[] getgroups(): pass  # Unix only, behaves differently on Mac
#void initgroups(str username, int gid): pass  # Unix only
str getlogin(): pass
#int getpgid(pid): pass  # Unix only
#int getpgrp(): pass  # Unix only
int getpid(): pass
int getppid(): pass
#int[] getresuid(): pass  # Unix only, returns 3-tuple of int
#int[] getresgid(): pass  # Unix only, returns 3-tuple of int
int getuid(): pass  # Unix only
str getenv(str key, str default=None): pass
bytes getenvb(bytes key, bytes default=None): pass
# TODO mixed str/bytes putenv arguments
void putenv(str key, str value): pass
void putenv(bytes key, bytes value): pass
#void setegid(int egid): pass  # Unix only
#void seteuid(int euid): pass  # Unix only
#void setgid(int gid): pass  # Unix only
#void setgroups(int[] groups): pass  # Unix only
#int setpgrp(): pass  # Unix only
#int setpgid(int pid, int pgrp): pass  # Unix only
#void setregid(int rgid, int egid): pass  # Unix only
#void setresgid(int rgid, int egid, int sgid): pass  # Unix only
#void setresuid(int ruid, int euid, int suid): pass  # Unix only
#void setreuid(int ruid, int euid): pass  # Unix only
#int getsid(int pid): pass  # Unix only
#int setsid(): pass  # Unix only
#void setuid(uid): pass  # Unix only
str strerror(int code): pass
int umask(int mask): pass
#str[] uname(): pass  # Unix only, reurns 5-tuple of str
void unsetenv(str key): pass
IO fdopen(int fd, str file, int flags, int mode=0o777): pass
void close(int fd): pass
void closerange(int fd_low, int fd_high): pass
str device_encoding(int fd): pass # May return None
int dup(int fd): pass
void dup2(fd, fd2): pass
#void fchmod(int fd, intmode): pass  # Unix only
#void fchown(int fd, int uid, int gid): pass  # Unix only
#void fdatasync(int fd): pass  # Unix only, not Mac
#int fpathconf(int fd, str name): pass  # Unix only
stat_result fstat(int fd): pass
#statvfs_result fstatvfs(int fd): pass  # Unix only
void fsync(int fd): pass
#void ftruncate(int fd, int length): pass  # Unix only
#bool isatty(int fd): pass  # Unix only
int lseek(int fd, int pos, int how): pass
IO open(str file, int flags, int mode=0o777): pass
#tuple<int, int> openpty(): pass  # some flavors of Unix
tuple<int, int> pipe(): pass
str read(int fd, int n): pass  # TODO: maybe returns bytes for bin files?
#int tcgetpgrp(int fd): pass  # Unix only
#void tcsetpgrp(int fd, int pg): pass  # Unix only
#str ttyname(int fd): pass  # Unix only
int write(int fd, str string): pass
bool access(str path, int mode): pass
void chdir(str path): pass
void fchdir(int fd): pass
str getcwd(): pass
bytes getcwdb(): pass
#void chflags(str path, int flags): pass  # Unix only
#void chroot(str path): pass  # Unix only
void chmod(str path, int mode): pass
void chown(str path, int uid, int gid): pass  # Unix only
#void lchflags(str path, int flags): pass  # Unix only
#void lchmod(str path, int mode): pass  # Unix only
#void lchown(str path, int uid, int gid): pass  # Unix only
void link(str src, str link_name): pass
str[] listdir(str path='.'): pass
str lstat(str path): pass
#void mkfifo(path, int mode=0o666): pass  # Unix only
void mknod(str filename, int mode=0o600, int device=0): pass
int major(int device): pass
int minor(int device): pass
int makedev(int major, int minor): pass
void mkdir(str path, int mode=0o777): pass
void makedirs(str path, int mode=0o777, bool exist_ok=False): pass
#int pathconf(str path, str name): pass  # Unix only
str readlink(str path): pass
void remove(str path): pass
void removedirs(str path): pass
void rename(str src, str dst): pass
void renames(str old, str new): pass
void rmdir(str path): pass
stat_result stat(str path): pass
bool stat_float_times(): pass
bool stat_float_times(bool newvalue): pass
#statvfs_result statvfs(str path): pass # Unix only
#void symlink(str source, str link_name): pass  # Unix only
#void symlink(str source, str link_name, bool target_is_directory=False):
#    pass  # Windows only
void unlink(str path): pass
void utime(str path, tuple<int, int> times=None): pass
void utime(str path, tuple<float, float> times=None): pass
# TODO onerror: function from OSError to void
str[] walk(str top, bool topdown=True, any onerror=None, 
               bool followlinks=False): 
    pass
# walk(): "By default errors from the os.listdir() call are ignored.  If
# optional arg 'onerror' is specified, it should be a function; it
# will be called with one argument, an os.error instance.  It can
# report the error to continue with the walk, or raise the exception
# to abort the walk.  Note that the filename is available as the
# filename attribute of the exception object."
void abort(): pass
void execl(str path, str[] args): pass # TODO fix
void execle(str path, str[] args, dict<str, str> env): pass # TODO fix
void execlp(str path, str[] args): pass # TODO fix
void execlpe(str path, str[] args, dict<str, str> env): pass # TODO fix
void execv(str path, str[] args): pass
void execve(str path, str[] args, dict<str, str> env): pass
void execvp(str file, str[] args): pass
void execvpe(str file, str[] args, dict<str, str> env): pass
void _exit(int n): pass
#int fork(): pass  # Unix only
#tuple<int, int> forkpty(): pass  # some flavors of Unix
void kill(int pid, int sig): pass
#void killpg(int pgid, int sig): pass  # Unix only
#int nice(int increment): pass  # Unix only
#void plock(int op): pass  # Unix only ???op is int?

# TODO return type
IO popen(str command, str mode='r', int bufsize=-1): pass  # TODO: params???

int spawnl(int mode, str path, str[] args): pass # TODO fix
int spawnle(int mode, str path, str[] args,
            dict<str, str> env): pass # TODO fix
int spawnlp(int mode, IO file, str[] args): pass  # Unix only TODO fix
int spawnlpe(int mode, IO file, str[] args, dict<str, str> env): 
    pass  # Unix only TODO fix
int spawnv(int mode, str path, str[] args): pass
int spawnve(int mode, str path, str[] args, dict<str, str> env): pass
int spawnvp(int mode, IO file, str[] args): pass  # Unix only
int spawnvpe(int mode, IO file, str[] args, dict<str, str> env): 
    pass  # Unix only
#void startfile(str path): pass  # Windows only
#void startfile(str path, str operation): pass  # Windows only
#tuple<int, int> system(str command): pass  # Unix only
int system(str command): pass
float[] times(): pass  # actually returns a 5-tuple of float
#tuple<int, int> wait(): pass  # Unix only
tuple<int, int> waitpid(int pid, int options): pass
#tuple<int, int, object> wait3(): pass  # Unix only
#tuple<int, int, object> wait3(int options): pass  # Unix only
#tuple<int, int, object> wait4(int pid, int options): pass  # Unix only
#bool WCOREDUMP(object status): pass  # Unix only
#bool WIFCONTINUED(object status): pass  # Unix only
#bool WIFSTOPPED(object status): pass  # Unix only
#bool WIFSIGNALED(object status): pass  # Unix only
#bool WIFEXITED(object status): pass  # Unix only
#bool WEXITSTATUS(object status): pass  # Unix only
#bool WSTOPSIG(object status): pass  # Unix only
#bool WTERMSIG(object status): pass  # Unix only
#str? confstr(str name): pass  # Unix only
#tuple<float, float, float> getloadavg(): pass  # Unix only
#int sysconf(str name): pass  # Unix only
bytes urandom(int n): pass
