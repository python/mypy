from __future__ import annotations

import typing as t

KT = t.TypeVar("KT")


class MyKeysView(t.KeysView[KT]):
    pass


d: dict[t.Any, t.Any] = {}
dict_keys = type(d.keys())

# This should not cause an error like `Member "register" is unknown`:
MyKeysView.register(dict_keys)
