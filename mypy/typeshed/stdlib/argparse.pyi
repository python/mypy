import sys
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NoReturn,
    Optional,
    Pattern,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

_T = TypeVar("_T")
_ActionT = TypeVar("_ActionT", bound=Action)
_N = TypeVar("_N")

ONE_OR_MORE: str
OPTIONAL: str
PARSER: str
REMAINDER: str
SUPPRESS: str
ZERO_OR_MORE: str
_UNRECOGNIZED_ARGS_ATTR: str  # undocumented

class ArgumentError(Exception):
    argument_name: Optional[str]
    message: str
    def __init__(self, argument: Optional[Action], message: str) -> None: ...

# undocumented
class _AttributeHolder:
    def _get_kwargs(self) -> List[Tuple[str, Any]]: ...
    def _get_args(self) -> List[Any]: ...

# undocumented
class _ActionsContainer:
    description: Optional[str]
    prefix_chars: str
    argument_default: Any
    conflict_handler: str

    _registries: Dict[str, Dict[Any, Any]]
    _actions: List[Action]
    _option_string_actions: Dict[str, Action]
    _action_groups: List[_ArgumentGroup]
    _mutually_exclusive_groups: List[_MutuallyExclusiveGroup]
    _defaults: Dict[str, Any]
    _negative_number_matcher: Pattern[str]
    _has_negative_number_optionals: List[bool]
    def __init__(self, description: Optional[str], prefix_chars: str, argument_default: Any, conflict_handler: str) -> None: ...
    def register(self, registry_name: str, value: Any, object: Any) -> None: ...
    def _registry_get(self, registry_name: str, value: Any, default: Any = ...) -> Any: ...
    def set_defaults(self, **kwargs: Any) -> None: ...
    def get_default(self, dest: str) -> Any: ...
    def add_argument(
        self,
        *name_or_flags: str,
        action: Union[str, Type[Action]] = ...,
        nargs: Union[int, str] = ...,
        const: Any = ...,
        default: Any = ...,
        type: Union[Callable[[str], _T], Callable[[str], _T], FileType] = ...,
        choices: Optional[Iterable[_T]] = ...,
        required: bool = ...,
        help: Optional[str] = ...,
        metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
        dest: Optional[str] = ...,
        version: str = ...,
        **kwargs: Any,
    ) -> Action: ...
    def add_argument_group(self, *args: Any, **kwargs: Any) -> _ArgumentGroup: ...
    def add_mutually_exclusive_group(self, **kwargs: Any) -> _MutuallyExclusiveGroup: ...
    def _add_action(self, action: _ActionT) -> _ActionT: ...
    def _remove_action(self, action: Action) -> None: ...
    def _add_container_actions(self, container: _ActionsContainer) -> None: ...
    def _get_positional_kwargs(self, dest: str, **kwargs: Any) -> Dict[str, Any]: ...
    def _get_optional_kwargs(self, *args: Any, **kwargs: Any) -> Dict[str, Any]: ...
    def _pop_action_class(self, kwargs: Any, default: Optional[Type[Action]] = ...) -> Type[Action]: ...
    def _get_handler(self) -> Callable[[Action, Iterable[Tuple[str, Action]]], Any]: ...
    def _check_conflict(self, action: Action) -> None: ...
    def _handle_conflict_error(self, action: Action, conflicting_actions: Iterable[Tuple[str, Action]]) -> NoReturn: ...
    def _handle_conflict_resolve(self, action: Action, conflicting_actions: Iterable[Tuple[str, Action]]) -> None: ...

class _FormatterClass(Protocol):
    def __call__(self, prog: str) -> HelpFormatter: ...

class ArgumentParser(_AttributeHolder, _ActionsContainer):
    prog: str
    usage: Optional[str]
    epilog: Optional[str]
    formatter_class: _FormatterClass
    fromfile_prefix_chars: Optional[str]
    add_help: bool
    allow_abbrev: bool

    # undocumented
    _positionals: _ArgumentGroup
    _optionals: _ArgumentGroup
    _subparsers: Optional[_ArgumentGroup]

    if sys.version_info >= (3, 9):
        def __init__(
            self,
            prog: Optional[str] = ...,
            usage: Optional[str] = ...,
            description: Optional[str] = ...,
            epilog: Optional[str] = ...,
            parents: Sequence[ArgumentParser] = ...,
            formatter_class: _FormatterClass = ...,
            prefix_chars: str = ...,
            fromfile_prefix_chars: Optional[str] = ...,
            argument_default: Any = ...,
            conflict_handler: str = ...,
            add_help: bool = ...,
            allow_abbrev: bool = ...,
            exit_on_error: bool = ...,
        ) -> None: ...
    else:
        def __init__(
            self,
            prog: Optional[str] = ...,
            usage: Optional[str] = ...,
            description: Optional[str] = ...,
            epilog: Optional[str] = ...,
            parents: Sequence[ArgumentParser] = ...,
            formatter_class: _FormatterClass = ...,
            prefix_chars: str = ...,
            fromfile_prefix_chars: Optional[str] = ...,
            argument_default: Any = ...,
            conflict_handler: str = ...,
            add_help: bool = ...,
            allow_abbrev: bool = ...,
        ) -> None: ...
    # The type-ignores in these overloads should be temporary.  See:
    # https://github.com/python/typeshed/pull/2643#issuecomment-442280277
    @overload
    def parse_args(self, args: Optional[Sequence[str]] = ...) -> Namespace: ...
    @overload
    def parse_args(self, args: Optional[Sequence[str]], namespace: None) -> Namespace: ...  # type: ignore
    @overload
    def parse_args(self, args: Optional[Sequence[str]], namespace: _N) -> _N: ...
    @overload
    def parse_args(self, *, namespace: None) -> Namespace: ...  # type: ignore
    @overload
    def parse_args(self, *, namespace: _N) -> _N: ...
    if sys.version_info >= (3, 7):
        def add_subparsers(
            self,
            *,
            title: str = ...,
            description: Optional[str] = ...,
            prog: str = ...,
            parser_class: Type[ArgumentParser] = ...,
            action: Type[Action] = ...,
            option_string: str = ...,
            dest: Optional[str] = ...,
            required: bool = ...,
            help: Optional[str] = ...,
            metavar: Optional[str] = ...,
        ) -> _SubParsersAction: ...
    else:
        def add_subparsers(
            self,
            *,
            title: str = ...,
            description: Optional[str] = ...,
            prog: str = ...,
            parser_class: Type[ArgumentParser] = ...,
            action: Type[Action] = ...,
            option_string: str = ...,
            dest: Optional[str] = ...,
            help: Optional[str] = ...,
            metavar: Optional[str] = ...,
        ) -> _SubParsersAction: ...
    def print_usage(self, file: Optional[IO[str]] = ...) -> None: ...
    def print_help(self, file: Optional[IO[str]] = ...) -> None: ...
    def format_usage(self) -> str: ...
    def format_help(self) -> str: ...
    def parse_known_args(
        self, args: Optional[Sequence[str]] = ..., namespace: Optional[Namespace] = ...
    ) -> Tuple[Namespace, List[str]]: ...
    def convert_arg_line_to_args(self, arg_line: str) -> List[str]: ...
    def exit(self, status: int = ..., message: Optional[str] = ...) -> NoReturn: ...
    def error(self, message: str) -> NoReturn: ...
    if sys.version_info >= (3, 7):
        def parse_intermixed_args(
            self, args: Optional[Sequence[str]] = ..., namespace: Optional[Namespace] = ...
        ) -> Namespace: ...
        def parse_known_intermixed_args(
            self, args: Optional[Sequence[str]] = ..., namespace: Optional[Namespace] = ...
        ) -> Tuple[Namespace, List[str]]: ...
    # undocumented
    def _get_optional_actions(self) -> List[Action]: ...
    def _get_positional_actions(self) -> List[Action]: ...
    def _parse_known_args(self, arg_strings: List[str], namespace: Namespace) -> Tuple[Namespace, List[str]]: ...
    def _read_args_from_files(self, arg_strings: List[str]) -> List[str]: ...
    def _match_argument(self, action: Action, arg_strings_pattern: str) -> int: ...
    def _match_arguments_partial(self, actions: Sequence[Action], arg_strings_pattern: str) -> List[int]: ...
    def _parse_optional(self, arg_string: str) -> Optional[Tuple[Optional[Action], str, Optional[str]]]: ...
    def _get_option_tuples(self, option_string: str) -> List[Tuple[Action, str, Optional[str]]]: ...
    def _get_nargs_pattern(self, action: Action) -> str: ...
    def _get_values(self, action: Action, arg_strings: List[str]) -> Any: ...
    def _get_value(self, action: Action, arg_string: str) -> Any: ...
    def _check_value(self, action: Action, value: Any) -> None: ...
    def _get_formatter(self) -> HelpFormatter: ...
    def _print_message(self, message: str, file: Optional[IO[str]] = ...) -> None: ...

class HelpFormatter:
    # undocumented
    _prog: str
    _indent_increment: int
    _max_help_position: int
    _width: int
    _current_indent: int
    _level: int
    _action_max_length: int
    _root_section: Any
    _current_section: Any
    _whitespace_matcher: Pattern[str]
    _long_break_matcher: Pattern[str]
    _Section: Type[Any]  # Nested class
    def __init__(
        self, prog: str, indent_increment: int = ..., max_help_position: int = ..., width: Optional[int] = ...
    ) -> None: ...
    def _indent(self) -> None: ...
    def _dedent(self) -> None: ...
    def _add_item(self, func: Callable[..., str], args: Iterable[Any]) -> None: ...
    def start_section(self, heading: Optional[str]) -> None: ...
    def end_section(self) -> None: ...
    def add_text(self, text: Optional[str]) -> None: ...
    def add_usage(
        self, usage: Optional[str], actions: Iterable[Action], groups: Iterable[_ArgumentGroup], prefix: Optional[str] = ...
    ) -> None: ...
    def add_argument(self, action: Action) -> None: ...
    def add_arguments(self, actions: Iterable[Action]) -> None: ...
    def format_help(self) -> str: ...
    def _join_parts(self, part_strings: Iterable[str]) -> str: ...
    def _format_usage(
        self, usage: str, actions: Iterable[Action], groups: Iterable[_ArgumentGroup], prefix: Optional[str]
    ) -> str: ...
    def _format_actions_usage(self, actions: Iterable[Action], groups: Iterable[_ArgumentGroup]) -> str: ...
    def _format_text(self, text: str) -> str: ...
    def _format_action(self, action: Action) -> str: ...
    def _format_action_invocation(self, action: Action) -> str: ...
    def _metavar_formatter(self, action: Action, default_metavar: str) -> Callable[[int], Tuple[str, ...]]: ...
    def _format_args(self, action: Action, default_metavar: str) -> str: ...
    def _expand_help(self, action: Action) -> str: ...
    def _iter_indented_subactions(self, action: Action) -> Generator[Action, None, None]: ...
    def _split_lines(self, text: str, width: int) -> List[str]: ...
    def _fill_text(self, text: str, width: int, indent: str) -> str: ...
    def _get_help_string(self, action: Action) -> Optional[str]: ...
    def _get_default_metavar_for_optional(self, action: Action) -> str: ...
    def _get_default_metavar_for_positional(self, action: Action) -> str: ...

class RawDescriptionHelpFormatter(HelpFormatter): ...
class RawTextHelpFormatter(RawDescriptionHelpFormatter): ...
class ArgumentDefaultsHelpFormatter(HelpFormatter): ...
class MetavarTypeHelpFormatter(HelpFormatter): ...

class Action(_AttributeHolder):
    option_strings: Sequence[str]
    dest: str
    nargs: Optional[Union[int, str]]
    const: Any
    default: Any
    type: Union[Callable[[str], Any], FileType, None]
    choices: Optional[Iterable[Any]]
    required: bool
    help: Optional[str]
    metavar: Optional[Union[str, Tuple[str, ...]]]
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = ...,
        const: Optional[_T] = ...,
        default: Union[_T, str, None] = ...,
        type: Optional[Union[Callable[[str], _T], Callable[[str], _T], FileType]] = ...,
        choices: Optional[Iterable[_T]] = ...,
        required: bool = ...,
        help: Optional[str] = ...,
        metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
    ) -> None: ...
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = ...,
    ) -> None: ...
    if sys.version_info >= (3, 9):
        def format_usage(self) -> str: ...

if sys.version_info >= (3, 9):
    class BooleanOptionalAction(Action):
        def __init__(
            self,
            option_strings: Sequence[str],
            dest: str,
            default: Union[_T, str, None] = ...,
            type: Optional[Union[Callable[[str], _T], Callable[[str], _T], FileType]] = ...,
            choices: Optional[Iterable[_T]] = ...,
            required: bool = ...,
            help: Optional[str] = ...,
            metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
        ) -> None: ...

class Namespace(_AttributeHolder):
    def __init__(self, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any) -> None: ...
    def __contains__(self, key: str) -> bool: ...

class FileType:
    # undocumented
    _mode: str
    _bufsize: int
    _encoding: Optional[str]
    _errors: Optional[str]
    def __init__(
        self, mode: str = ..., bufsize: int = ..., encoding: Optional[str] = ..., errors: Optional[str] = ...
    ) -> None: ...
    def __call__(self, string: str) -> IO[Any]: ...

# undocumented
class _ArgumentGroup(_ActionsContainer):
    title: Optional[str]
    _group_actions: List[Action]
    def __init__(
        self, container: _ActionsContainer, title: Optional[str] = ..., description: Optional[str] = ..., **kwargs: Any
    ) -> None: ...

# undocumented
class _MutuallyExclusiveGroup(_ArgumentGroup):
    required: bool
    _container: _ActionsContainer
    def __init__(self, container: _ActionsContainer, required: bool = ...) -> None: ...

# undocumented
class _StoreAction(Action): ...

# undocumented
class _StoreConstAction(Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        const: Any,
        default: Any = ...,
        required: bool = ...,
        help: Optional[str] = ...,
        metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
    ) -> None: ...

# undocumented
class _StoreTrueAction(_StoreConstAction):
    def __init__(
        self, option_strings: Sequence[str], dest: str, default: bool = ..., required: bool = ..., help: Optional[str] = ...
    ) -> None: ...

# undocumented
class _StoreFalseAction(_StoreConstAction):
    def __init__(
        self, option_strings: Sequence[str], dest: str, default: bool = ..., required: bool = ..., help: Optional[str] = ...
    ) -> None: ...

# undocumented
class _AppendAction(Action): ...

# undocumented
class _AppendConstAction(Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        const: Any,
        default: Any = ...,
        required: bool = ...,
        help: Optional[str] = ...,
        metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
    ) -> None: ...

# undocumented
class _CountAction(Action):
    def __init__(
        self, option_strings: Sequence[str], dest: str, default: Any = ..., required: bool = ..., help: Optional[str] = ...
    ) -> None: ...

# undocumented
class _HelpAction(Action):
    def __init__(self, option_strings: Sequence[str], dest: str = ..., default: str = ..., help: Optional[str] = ...) -> None: ...

# undocumented
class _VersionAction(Action):
    version: Optional[str]
    def __init__(
        self, option_strings: Sequence[str], version: Optional[str] = ..., dest: str = ..., default: str = ..., help: str = ...
    ) -> None: ...

# undocumented
class _SubParsersAction(Action):
    _ChoicesPseudoAction: Type[Any]  # nested class
    _prog_prefix: str
    _parser_class: Type[ArgumentParser]
    _name_parser_map: Dict[str, ArgumentParser]
    choices: Dict[str, ArgumentParser]
    _choices_actions: List[Action]
    if sys.version_info >= (3, 7):
        def __init__(
            self,
            option_strings: Sequence[str],
            prog: str,
            parser_class: Type[ArgumentParser],
            dest: str = ...,
            required: bool = ...,
            help: Optional[str] = ...,
            metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
        ) -> None: ...
    else:
        def __init__(
            self,
            option_strings: Sequence[str],
            prog: str,
            parser_class: Type[ArgumentParser],
            dest: str = ...,
            help: Optional[str] = ...,
            metavar: Optional[Union[str, Tuple[str, ...]]] = ...,
        ) -> None: ...
    # TODO: Type keyword args properly.
    def add_parser(self, name: str, **kwargs: Any) -> ArgumentParser: ...
    def _get_subactions(self) -> List[Action]: ...

# undocumented
class ArgumentTypeError(Exception): ...

if sys.version_info < (3, 7):
    # undocumented
    def _ensure_value(namespace: Namespace, name: str, value: Any) -> Any: ...

# undocumented
def _get_action_name(argument: Optional[Action]) -> Optional[str]: ...
