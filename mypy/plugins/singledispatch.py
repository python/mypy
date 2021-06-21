from mypy.checker import TypeChecker
from mypy.subtypes import is_subtype
from mypy.types import CallableType, Instance, Type, get_proper_type
from mypy.plugin import FunctionContext, MethodContext, MethodSigContext
from typing import List, Optional, Set, TypeVar, cast
from typing_extensions import TypedDict

SingledispatchInfo = TypedDict('SingledispatchInfo', {
    'fallback': CallableType,
    # use a set to make sure we don't add the same function multiple times if the register
    # callback gets called multiple times
    'registered': Set[CallableType],
})

SINGLEDISPATCH_TYPE = 'functools._SingleDispatchCallable'

# key that we use for everything we store in TypeInfo metadata
METADATA_KEY = 'singledispatch'


def get_singledispatch_info(typ: Instance) -> 'SingledispatchInfo':
    return typ.type.metadata[METADATA_KEY]  # type: ignore


T = TypeVar('T')


def get_first_arg(args: List[List[T]]) -> Optional[T]:
    """Get the element that corresponds to the first argument passed to the function"""
    if args and args[0]:
        return args[0][0]
    return None


def create_singledispatch_function_callback(ctx: FunctionContext) -> Type:
    # TODO: check that there's only one argument
    func_type = get_proper_type(get_first_arg(ctx.arg_types))
    if isinstance(func_type, CallableType):
        # TODO: support using type as argument to register
        metadata = {
            'fallback': func_type,
            'registered': set()
        }  # type: SingledispatchInfo

        # singledispatch returns an instance of functools._SingleDispatchCallable according to
        # typeshed
        singledispatch_obj = get_proper_type(ctx.default_return_type)
        assert isinstance(singledispatch_obj, Instance)
        # mypy shows an error when assigning TypedDict to a regular dict
        singledispatch_obj.type.metadata[METADATA_KEY] = metadata  # type: ignore

    return ctx.default_return_type


def singledispatch_register_callback(ctx: MethodContext) -> Type:
    # TODO: support passing class to register as argument (and add tests for that)
    if isinstance(ctx.type, Instance):
        metadata = get_singledispatch_info(ctx.type)
        # TODO: check that there's only one argument
        first_arg_type = get_proper_type(get_first_arg(ctx.arg_types))
        if isinstance(first_arg_type, CallableType):
            # TODO: do more checking for registered functions
            metadata['registered'].add(first_arg_type)

    # register doesn't modify the function it's used on
    return ctx.default_return_type


def call_singledispatch_function_callback(ctx: MethodSigContext) -> CallableType:
    if not isinstance(ctx.type, Instance):
        return ctx.default_signature
    metadata = get_singledispatch_info(ctx.type)
    first_arg = get_first_arg(ctx.args)
    if first_arg is None:
        return ctx.default_signature
    # TODO: find a way to get the type of the first argument with the public API
    # (expr_checker probably isn't part of the public API)
    passed_type = cast(TypeChecker, ctx.api).expr_checker.accept(first_arg)
    for func in metadata['registered']:
        if func.arg_types:
            sig_type = func.arg_types[0]
            if is_subtype(passed_type, sig_type):
                # TODO: Should error messages relating to registered functions use fallback's name
                # or registered name?
                return func
    return metadata['fallback']
