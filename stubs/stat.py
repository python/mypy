# Stubs for stat

# Based on http://docs.python.org/3.2/library/stat.html

bool S_ISDIR(int mode): pass
bool S_ISCHR(int mode): pass
bool S_ISBLK(int mode): pass
bool S_ISREG(int mode): pass
bool S_ISFIFO(int mode): pass
bool S_ISLNK(int mode): pass
bool S_ISSOCK(int mode): pass

int S_IMODE(int mode): pass
int S_IFMT(mode): pass

int ST_MODE
int ST_INO
int ST_DEV
int ST_NLINK
int ST_UID
int ST_GID
int ST_SIZE
int ST_ATIME
int ST_MTIME
int ST_CTIME

int S_IFSOCK
int S_IFLNK
int S_IFREG
int S_IFBLK
int S_IFDIR
int S_IFCHR
int S_IFIFO
int S_ISUID
int S_ISGID
int S_ISVTX

int S_IRWXU
int S_IRUSR
int S_IWUSR
int S_IXUSR

int S_IRWXG
int S_IRGRP
int S_IWGRP
int S_IXGRP

int S_IRWXO
int S_IROTH
int S_IWOTH
int S_IXOTH

int S_ENFMT
int S_IREAD
int S_IWRITE
int S_IEXEC

int UF_NODUMP
int UF_IMMUTABLE
int UF_APPEND
int UF_OPAQUE
int UF_NOUNLINK
#int UF_COMPRESSED # OS X 10.6+ only
#int UF_HIDDEN     # OX X 10.5+ only
int SF_ARCHIVED
int SF_IMMUTABLE
int SF_APPEND
int SF_NOUNLINK
int SF_SNAPSHOT
