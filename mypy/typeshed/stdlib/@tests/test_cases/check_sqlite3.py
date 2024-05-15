from __future__ import annotations

import sqlite3
from typing_extensions import assert_type


class MyConnection(sqlite3.Connection):
    pass


# Default return-type is Connection.
assert_type(sqlite3.connect(":memory:"), sqlite3.Connection)

# Providing an alternate factory changes the return-type.
assert_type(sqlite3.connect(":memory:", factory=MyConnection), MyConnection)

# Provides a true positive error. When checking the connect() function,
# mypy should report an arg-type error for the factory argument.
with sqlite3.connect(":memory:", factory=None) as con:  # type: ignore
    pass

# The Connection class also accepts a `factory` arg but it does not affect
# the return-type. This use case is not idiomatic--connections should be
# established using the `connect()` function, not directly (as shown here).
assert_type(sqlite3.Connection(":memory:", factory=None), sqlite3.Connection)
assert_type(sqlite3.Connection(":memory:", factory=MyConnection), sqlite3.Connection)
