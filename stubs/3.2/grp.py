from typing import List, Undefined

# TODO group database entry object type

class struct_group:
    gr_name = ''
    gr_passwd = ''
    gr_gid = 0
    gr_mem = Undefined(List[str])

def getgrgid(gid: int) -> struct_group: pass
def getgrnam(name: str) -> struct_group: pass
def getgrall() -> List[struct_group]: pass
