# Stubs for pwd

# NOTE: These are incomplete!

import typing

class struct_passwd:
    # TODO use namedtuple
    pw_name = ''
    pw_passwd = ''
    pw_uid = 0
    pw_gid = 0
    pw_gecos = ''
    pw_dir = ''
    pw_shell = ''

def getpwuid(uid: int) -> struct_passwd: pass
def getpwnam(name: str) -> struct_passwd: pass
