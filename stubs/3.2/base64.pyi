# Stubs for base64

# Based on http://docs.python.org/3.2/library/base64.html

from typing import IO

def b64encode(s: bytes, altchars: bytes = None) -> bytes: pass
def b64decode(s: bytes, altchars: bytes = None,
              validate: bool = False) -> bytes: pass
def standard_b64encode(s: bytes) -> bytes: pass
def standard_b64decode(s: bytes) -> bytes: pass
def urlsafe_b64encode(s: bytes) -> bytes: pass
def urlsafe_b64decode(s: bytes) -> bytes: pass
def b32encode(s: bytes) -> bytes: pass
def b32decode(s: bytes, casefold: bool = False,
              map01: bytes = None) -> bytes: pass
def b16encode(s: bytes) -> bytes: pass
def b16decode(s: bytes, casefold: bool = False) -> bytes: pass

def decode(input: IO[bytes], output: IO[bytes]) -> None: pass
def decodebytes(s: bytes) -> bytes: pass
def decodestring(s: bytes) -> bytes: pass
def encode(input: IO[bytes], output: IO[bytes]) -> None: pass
def encodebytes(s: bytes) -> bytes: pass
def encodestring(s: bytes) -> bytes: pass
