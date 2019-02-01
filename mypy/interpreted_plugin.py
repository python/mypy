"""Hack for handling non-mypyc compiled plugins with a mypyc-compiled mypy"""

from typing import Optional, Callable, Any, Dict
from mypy.options import Options
from mypy.types import Type, CallableType
from mypy.nodes import SymbolTableNode, MypyFile
from mypy.lookup import lookup_fully_qualified

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
        plugin = object.__new__(cls)
        plugin.__init__(*args, **kwargs)
        return WrapperPlugin(plugin)

    def __init__(self, options: Options) -> None:
        self.options = options
        self.python_version = options.python_version
        self._modules = None  # type: Optional[Dict[str, MypyFile]]

    def set_modules(self, modules: Dict[str, MypyFile]) -> None:
        self._modules = modules

    def lookup_fully_qualified(self, fullname: str) -> Optional[SymbolTableNode]:
        assert self._modules is not None
        return lookup_fully_qualified(fullname, self._modules)

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

    def get_dynamic_class_hook(self, fullname: str
                               ) -> Optional[Callable[['mypy.plugin.DynamicClassDefContext'],
                                                      None]]:
        return None
