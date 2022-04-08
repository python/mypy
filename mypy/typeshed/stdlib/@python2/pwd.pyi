import sys

if sys.platform != "win32":
    class struct_passwd(tuple[str, str, int, int, str, str, str]):
        pw_name: str
        pw_passwd: str
        pw_uid: int
        pw_gid: int
        pw_gecos: str
        pw_dir: str
        pw_shell: str
    def getpwall() -> list[struct_passwd]: ...
    def getpwuid(__uid: int) -> struct_passwd: ...
    def getpwnam(__name: str) -> struct_passwd: ...
