"""Stuff that we had to move out of its right place because of mypyc limitations."""

# Moved from util.py, because it inherits from Exception
class DecodeError(Exception):
    """Exception raised when a file cannot be decoded due to an unknown encoding type.

    Essentially a wrapper for the LookupError raised by `bytearray.decode`
    """
