from typing import Any, typevar
from asyncio.events import AbstractEventLoop
# __all__ = ['coroutine', 'Task',
#            'iscoroutinefunction', 'iscoroutine',
#            'FIRST_COMPLETED', 'FIRST_EXCEPTION', 'ALL_COMPLETED',
#            'wait', 'wait_for', 'as_completed', 'sleep', 'async',
#            'gather', 'shield',
#            ]

__all__ = ['coroutine', 'sleep']

_T = typevar('_T')
def coroutine(f: Any) -> Any: pass
def sleep(delay: float, result: _T=None, loop: AbstractEventLoop=None) -> _T: pass
