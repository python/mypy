# Stubs for hashlib

# NOTE: These are incomplete!

from abc import abstractmethod, ABCMeta
import typing

class Hash(metaclass=ABCMeta):
    @abstractmethod
    def update(self, arg: bytes) -> None: pass
    @abstractmethod
    def digest(self) -> bytes: pass
    @abstractmethod
    def hexdigest(self) -> str: pass
    @abstractmethod
    def copy(self) -> 'Hash': pass

def md5(arg: bytes = None) -> Hash: pass
def sha1(arg: bytes = None) -> Hash: pass
def sha224(arg: bytes = None) -> Hash: pass
def sha256(arg: bytes = None) -> Hash: pass
def sha384(arg: bytes = None) -> Hash: pass
def sha512(arg: bytes = None) -> Hash: pass

def new(name: str, data: bytes = None) -> Hash: pass
