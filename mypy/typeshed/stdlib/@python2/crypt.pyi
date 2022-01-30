import sys

if sys.platform != "win32":
    def crypt(word: str, salt: str) -> str: ...
