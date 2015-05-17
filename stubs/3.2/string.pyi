# Stubs for string

# Based on http://docs.python.org/3.2/library/string.html

from typing import Mapping

ascii_letters = ''
ascii_lowercase = ''
ascii_uppercase = ''
digits = ''
hexdigits = ''
octdigits = ''
punctuation = ''
printable = ''
whitespace = ''

def capwords(s: str, sep: str = None) -> str: pass

class Template:
    template = ''

    def __init__(self, template: str) -> None: pass
    def substitute(self, mapping: Mapping[str, str], **kwds: str) -> str: pass
    def safe_substitute(self, mapping: Mapping[str, str],
                        **kwds: str) -> str: pass

# TODO Formatter
