from collections.abc import Awaitable, Callable
from typing_extensions import ParamSpec

from .case import TestCase

_P = ParamSpec("_P")

class IsolatedAsyncioTestCase(TestCase):
    async def asyncSetUp(self) -> None: ...
    async def asyncTearDown(self) -> None: ...
    def addAsyncCleanup(self, __func: Callable[_P, Awaitable[object]], *args: _P.args, **kwargs: _P.kwargs) -> None: ...
