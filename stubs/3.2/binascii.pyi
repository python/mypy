# Stubs for binascii

# Based on http://docs.python.org/3.2/library/binascii.html

import typing

def a2b_uu(string: bytes) -> bytes: pass
def b2a_uu(data: bytes) -> bytes: pass
def a2b_base64(string: bytes) -> bytes: pass
def b2a_base64(data: bytes) -> bytes: pass
def a2b_qp(string: bytes, header: bool = False) -> bytes: pass
def b2a_qp(data: bytes, quotetabs: bool = False, istext: bool = True,
             header: bool = False) -> bytes: pass
def a2b_hqx(string: bytes) -> bytes: pass
def rledecode_hqx(data: bytes) -> bytes: pass
def rlecode_hqx(data: bytes) -> bytes: pass
def b2a_hqx(data: bytes) -> bytes: pass
def crc_hqx(data: bytes, crc: int) -> int: pass
def crc32(data: bytes, crc: int = None) -> int: pass
def b2a_hex(data: bytes) -> bytes: pass
def hexlify(data: bytes) -> bytes: pass
def a2b_hex(hexstr: bytes) -> bytes: pass
def unhexlify(hexlify: bytes) -> bytes: pass

class Error(Exception): pass
class Incomplete(Exception): pass
