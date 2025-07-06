"""Constant definitions for singledispatch plugin moved here to help with import cycle."""

from typing import Final

SINGLEDISPATCH_TYPE: Final = "functools._SingleDispatchCallable"

SINGLEDISPATCH_REGISTER_METHOD: Final = f"{SINGLEDISPATCH_TYPE}.register"

SINGLEDISPATCH_CALLABLE_CALL_METHOD: Final = f"{SINGLEDISPATCH_TYPE}.__call__"

REGISTER_RETURN_CLASS: Final = "_SingleDispatchRegisterCallable"

REGISTER_CALLABLE_CALL_METHOD: Final = f"functools.{REGISTER_RETURN_CLASS}.__call__"
