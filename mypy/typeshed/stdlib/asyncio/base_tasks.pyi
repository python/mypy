from _typeshed import AnyPath
from typing import List, Optional
from types import FrameType
from . import tasks

def _task_repr_info(task: tasks.Task) -> List[str]: ...  # undocumented
def _task_get_stack(task: tasks.Task, limit: Optional[int]) -> List[FrameType]: ...  # undocumented
def _task_print_stack(task: tasks.Task, limit: Optional[int], file: AnyPath): ...  # undocumented
