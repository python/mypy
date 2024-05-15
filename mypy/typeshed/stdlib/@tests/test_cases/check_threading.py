from __future__ import annotations

import _threading_local
import threading

loc = threading.local()
loc.foo = 42
del loc.foo
loc.baz = ["spam", "eggs"]
del loc.baz

l2 = _threading_local.local()
l2.asdfasdf = 56
del l2.asdfasdf
