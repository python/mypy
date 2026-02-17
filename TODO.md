# TODO: Fix C string encoding in mypyc/codegen/cstring.py

## Issue
The current implementation uses octal escape sequences (`\XXX`) but the tests expect hex escape sequences (`\xXX`).

## Changes Needed
1. [x] Understand the expected behavior from tests in test_emitfunc.py
2. [x] Update CHAR_MAP to use hex escapes instead of octal escapes
3. [x] Keep simple escape sequences for special chars (\n, \r, \t, etc.)
4. [x] Update the docstring to reflect correct format (\xXX instead of \oXXX)

