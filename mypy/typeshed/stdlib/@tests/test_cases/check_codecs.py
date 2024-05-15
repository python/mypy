from __future__ import annotations

import codecs
from typing_extensions import assert_type

assert_type(codecs.decode("x", "unicode-escape"), str)
assert_type(codecs.decode(b"x", "unicode-escape"), str)

assert_type(codecs.decode(b"x", "utf-8"), str)
codecs.decode("x", "utf-8")  # type: ignore

assert_type(codecs.decode("ab", "hex"), bytes)
assert_type(codecs.decode(b"ab", "hex"), bytes)
