"""Hack for handling non-mypyc compiled plugins with a mypyc-compiled mypy"""

from typing import Optional, Callable, Any
from mypy.options import Options
from mypy.types import Type, CallableType


MYPY = False
if MYPY:
    import mypy.plugin


class InterpretedPlugin:
    """Base class of type checker plugins as exposed to external code.

    This is a hack around mypyc not currently supporting interpreted subclasses
    of compiled classes.
    mypy.plugin will arrange for interpreted code to be find this class when it looks
    for Plugin, and this class has a __new__ method that returns a WrapperPlugin object
    that proxies to this interpreted version.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> 'mypy.plugin.Plugin':
        from mypy.plugin import WrapperPlugin
        plugin = object.__new__(cls)  # type: ignore
        plugin.__init__(*args, **kwargs)
        return WrapperPlugin(plugin)

    def __init__(self, options: Options) -> None:
        self.options = options
        self.python_version = options.python_version

    def get_type_analyze_hook(self, fullname: str
                              ) -> Optional[Callable[['mypy.plugin.AnalyzeTypeContext'], Type]]:
        return None

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[['mypy.plugin.FunctionContext'], Type]]:
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[['mypy.plugin.MethodSigContext'],
                                                         CallableType]]:
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[['mypy.plugin.MethodContext'], Type]]:
        return None

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[['mypy.plugin.AttributeContext'], Type]]:
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[['mypy.plugin.ClassDefContext'], None]]:
        return None

    def get_metaclass_hook(self, fullname: str
                           ) -> Optional[Callable[['mypy.plugin.ClassDefContext'], None]]:
        return None

    def get_base_class_hook(self, fullname: str
                            ) -> Optional[Callable[['mypy.plugin.ClassDefContext'], None]]:
        return None

    def get_customize_class_mro_hook(self, fullname: str
                                     ) -> Optional[Callable[['mypy.plugin.ClassDefContext'],
                                                            None]]:
        return None
