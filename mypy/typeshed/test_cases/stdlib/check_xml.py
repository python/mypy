from __future__ import annotations

import sys
from typing_extensions import assert_type
from xml.dom.minidom import Document

document = Document()

assert_type(document.toxml(), str)
assert_type(document.toxml(encoding=None), str)
assert_type(document.toxml(encoding="UTF8"), bytes)
assert_type(document.toxml("UTF8"), bytes)
if sys.version_info >= (3, 9):
    assert_type(document.toxml(standalone=True), str)
    assert_type(document.toxml("UTF8", True), bytes)
    assert_type(document.toxml(encoding="UTF8", standalone=True), bytes)


# Because toprettyxml can mix positional and keyword variants of the "encoding" argument, which
# determines the return type, the proper stub typing isn't immediately obvious. This is a basic
# brute-force sanity check.
# Test cases like toxml
assert_type(document.toprettyxml(), str)
assert_type(document.toprettyxml(encoding=None), str)
assert_type(document.toprettyxml(encoding="UTF8"), bytes)
if sys.version_info >= (3, 9):
    assert_type(document.toprettyxml(standalone=True), str)
    assert_type(document.toprettyxml(encoding="UTF8", standalone=True), bytes)
# Test cases unique to toprettyxml
assert_type(document.toprettyxml("  "), str)
assert_type(document.toprettyxml("  ", "\r\n"), str)
assert_type(document.toprettyxml("  ", "\r\n", "UTF8"), bytes)
if sys.version_info >= (3, 9):
    assert_type(document.toprettyxml("  ", "\r\n", "UTF8", True), bytes)
    assert_type(document.toprettyxml("  ", "\r\n", standalone=True), str)
