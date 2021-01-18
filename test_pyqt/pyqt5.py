from typing import Callable, Optional
from typing import Type

from mypy.plugin import (
    Plugin, FunctionDecoratorContext,
)


def plugin(version: str) -> Type[Plugin]:
    return PyQt5Plugin


class PyQt5Plugin(Plugin):
    """PyQt5 Plugin"""

    def get_function_decorator_hook(self, fullname: str
                                    ) -> Optional[Callable[[FunctionDecoratorContext], None]]:
        if fullname == 'PyQt5.QtCore.pyqtProperty':
            return pyqt_property_callback
        return None


def pyqt_property_callback(ctx: FunctionDecoratorContext):
    ctx.decoratedFunction.func.is_property = True
