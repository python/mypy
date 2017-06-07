from typing import Optional

from mypy.plugin import Plugin, TypeAnalyzeHook, SemanticAnalysisPluginContext
from mypy.types import Type, UnboundType, TypeList, AnyType, NoneTyp, CallableType


class TypeAnalyzePlugin(Plugin):
    def get_type_analyze_hook(self, fullname: str) -> Optional[TypeAnalyzeHook]:
        if fullname == 'm.Signal':
            return signal_type_analyze_callback
        return None


def signal_type_analyze_callback(
        typ: UnboundType,
        context: SemanticAnalysisPluginContext) -> Type:
    if (len(typ.args) != 1
            or not isinstance(typ.args[0], TypeList)):
        context.fail('Invalid "Signal" type (expected "Signal[[t, ...]]")', context.context)
        return AnyType()

    args = typ.args[0]
    assert isinstance(args, TypeList)
    analyzed = context.analyze_arg_list(args)
    if analyzed is None:
        return AnyType()  # Error generated elsewhere
    arg_types, arg_kinds, arg_names = analyzed
    arg_types = [context.analyze_type(arg) for arg in arg_types]
    type_arg = CallableType(arg_types,
                            arg_kinds,
                            arg_names,
                            NoneTyp(),
                            context.named_instance('builtins.function', []))
    return context.named_instance('m.Signal', [type_arg])


def plugin(version):
    return TypeAnalyzePlugin
