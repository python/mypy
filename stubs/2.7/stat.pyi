def S_ISDIR(mode: int) -> bool: ...
def S_ISCHR(mode: int) -> bool: ...
def S_ISBLK(mode: int) -> bool: ...
def S_ISREG(mode: int) -> bool: ...
def S_ISFIFO(mode: int) -> bool: ...
def S_ISLNK(mode: int) -> bool: ...
def S_ISSOCK(mode: int) -> bool: ...

def S_IMODE(mode: int) -> int: ...
def S_IFMT(mode: int) -> int: ...

ST_MODE = 0
ST_INO = 0
ST_DEV = 0
ST_NLINK = 0
ST_UID = 0
ST_GID = 0
ST_SIZE = 0
ST_ATIME = 0
ST_MTIME = 0
ST_CTIME = 0
ST_IFSOCK = 0
ST_IFLNK = 0
ST_IFREG = 0
ST_IFBLK = 0
ST_IFDIR = 0
ST_IFCHR = 0
ST_IFIFO = 0
S_ISUID = 0
S_ISGID = 0
S_ISVTX = 0
S_IRWXU = 0
S_IRUSR = 0
S_IWUSR = 0
S_IXUSR = 0
S_IRGRP = 0
S_IWGRP = 0
S_IXGRP = 0
S_IRWXO = 0
S_IROTH = 0
S_IWOTH = 0
S_IXOTH = 0
S_ENFMT = 0
S_IREAD = 0
S_IWRITE = 0
S_IEXEC = 0
UF_NODUMP = 0
UF_IMMUTABLE = 0
UF_APPEND = 0
UF_OPAQUE = 0
UF_NOUNLINK = 0
UF_COMPRESSED = 0
UF_HIDDEN = 0
SF_ARCHIVED = 0
SF_IMMUTABLE = 0
SF_APPEND = 0
SF_NOUNLINK = 0
SF_SNAPSHOT = 0
