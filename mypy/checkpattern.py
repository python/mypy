"""Pattern checker. This file is conceptually part of TypeChecker."""
from typing import List, Optional, Union, Tuple

from mypy import message_registry
from mypy.expandtype import expand_type_by_instance
from mypy.join import join_types

from mypy.messages import MessageBuilder
from mypy.nodes import Expression, NameExpr, ARG_POS, TypeAlias, TypeInfo
from mypy.patterns import (
    Pattern, AsPattern, OrPattern, LiteralPattern, CapturePattern, WildcardPattern, ValuePattern,
    SequencePattern, StarredPattern, MappingPattern, ClassPattern, MappingKeyPattern
)
from mypy.plugin import Plugin
from mypy.subtypes import is_subtype, find_member, is_equivalent
from mypy.typeops import try_getting_str_literals_from_type
from mypy.types import (
    ProperType, AnyType, TypeOfAny, Instance, Type, NoneType, UninhabitedType, get_proper_type,
    TypedDictType, TupleType
)
from mypy.typevars import fill_typevars
from mypy.visitor import PatternVisitor
import mypy.checker


self_match_type_names = [
    "builtins.bool",
    "builtins.bytearray",
    "builtins.bytes",
    "builtins.dict",
    "builtins.float",
    "builtins.frozenset",
    "builtins.int",
    "builtins.list",
    "builtins.set",
    "builtins.str",
    "builtins.tuple",
]


class PatternChecker(PatternVisitor[Optional[Type]]):
    """Pattern checker.

    This class checks if a pattern can match a type, what the type can be narrowed to, and what
    type capture patterns should be inferred as.
    """

    # Some services are provided by a TypeChecker instance.
    chk = None  # type: mypy.checker.TypeChecker
    # This is shared with TypeChecker, but stored also here for convenience.
    msg = None  # type: MessageBuilder
    # Currently unused
    plugin = None  # type: Plugin
    # The expression being matched against the pattern
    subject = None  # type: Expression
    # Type of the subject to check the (sub)pattern against
    type_stack = []  # type: List[Type]

    self_match_types = None  # type: List[Type]

    def __init__(self, chk: 'mypy.checker.TypeChecker', msg: MessageBuilder, plugin: Plugin,
                 subject: Expression, subject_type: Type) -> None:
        self.chk = chk
        self.msg = msg
        self.plugin = plugin
        self.subject = subject
        self.type_stack.append(subject_type)

        self.self_match_types = self.generate_self_match_types()

    def check_pattern(self, o: Pattern) -> 'mypy.checker.TypeMap':
        pattern_type = self.visit(o)
        if pattern_type is None:
            # This case is unreachable
            return None
        elif is_equivalent(self.type_stack[-1], pattern_type):
            # No need to narrow
            return {}
        else:
            return {self.subject: pattern_type}

    def visit(self, o: Pattern) -> Optional[Type]:
        return o.accept(self)

    def visit_as_pattern(self, o: AsPattern) -> Optional[Type]:
        typ = self.visit(o.pattern)
        specific_type = get_more_specific_type(typ, self.type_stack[-1])
        if specific_type is None:
            return None
        self.type_stack.append(specific_type)
        self.check_capture(o.name)
        self.type_stack.pop()
        return typ

    def visit_or_pattern(self, o: OrPattern) -> Optional[Type]:
        return self.type_stack[-1]

    def visit_literal_pattern(self, o: LiteralPattern) -> Optional[Type]:
        literal_type = self.get_literal_type(o.value)
        return get_more_specific_type(literal_type, self.type_stack[-1])

    def get_literal_type(self, l: Union[int, complex, float, str, bytes, None]) -> Type:
        # TODO: Should we use ExprNodes instead of the raw value here?
        if isinstance(l, int):
            return self.chk.named_type("builtins.int")
        elif isinstance(l, complex):
            return self.chk.named_type("builtins.complex")
        elif isinstance(l, float):
            return self.chk.named_type("builtins.float")
        elif isinstance(l, str):
            return self.chk.named_type("builtins.str")
        elif isinstance(l, bytes):
            return self.chk.named_type("builtins.bytes")
        elif isinstance(l, bool):
            return self.chk.named_type("builtins.bool")
        elif l is None:
            return NoneType()
        else:
            assert False, "Invalid literal in literal pattern"

    def visit_capture_pattern(self, o: CapturePattern) -> Optional[Type]:
        self.check_capture(o.name)
        return self.type_stack[-1]

    def check_capture(self, capture: NameExpr) -> None:
        capture_type, _, inferred = self.chk.check_lvalue(capture)
        if capture_type:
            self.chk.check_subtype(capture_type, self.type_stack[-1], capture,
                                   msg=message_registry.INCOMPATIBLE_TYPES_IN_CAPTURE,
                                   subtype_label="pattern captures type",
                                   supertype_label="variable has type")
        else:
            assert inferred is not None
            self.chk.infer_variable_type(inferred, capture, self.type_stack[-1], self.subject)

    def visit_wildcard_pattern(self, o: WildcardPattern) -> Optional[Type]:
        return self.type_stack[-1]

    def visit_value_pattern(self, o: ValuePattern) -> Optional[Type]:
        typ = self.chk.expr_checker.accept(o.expr)
        return get_more_specific_type(typ, self.type_stack[-1])

    def visit_sequence_pattern(self, o: SequencePattern) -> Optional[Type]:
        current_type = self.type_stack[-1]
        inner_type = self.get_sequence_type(get_proper_type(current_type))
        if inner_type is None:
            if is_subtype(self.chk.named_type("typing.Iterable"), current_type):
                # Current type is more general, but the actual value could still be iterable
                inner_type = self.chk.named_type("builtins.object")
            else:
                # Pattern can't match
                return None

        assert isinstance(current_type, Instance)
        self.type_stack.append(inner_type)
        new_inner_type = UninhabitedType()  # type: Type
        for p in o.patterns:
            pattern_type = self.visit(p)
            if pattern_type is None:
                return None
            new_inner_type = join_types(new_inner_type, pattern_type)
        self.type_stack.pop()
        iterable = self.chk.named_generic_type("typing.Iterable", [new_inner_type])
        if self.chk.type_is_iterable(current_type):
            empty_type = fill_typevars(current_type.type)
            partial_type = expand_type_by_instance(empty_type, iterable)
            new_type = expand_type_by_instance(partial_type, current_type)
        else:
            new_type = iterable

        if is_subtype(new_type, current_type):
            return new_type
        else:
            return current_type

    def get_sequence_type(self, t: ProperType) -> Optional[Type]:
        if isinstance(t, AnyType):
            return AnyType(TypeOfAny.from_another_any, t)

        if self.chk.type_is_iterable(t) and isinstance(t, Instance):
            return self.chk.iterable_item_type(t)
        else:
            return None

    def visit_starred_pattern(self, o: StarredPattern) -> Optional[Type]:
        if not isinstance(o.capture, WildcardPattern):
            list_type = self.chk.named_generic_type('builtins.list', [self.type_stack[-1]])
            self.type_stack.append(list_type)
            self.visit_capture_pattern(o.capture)
            self.type_stack.pop()
        return self.type_stack[-1]

    def visit_mapping_pattern(self, o: MappingPattern) -> Optional[Type]:
        current_type = self.type_stack[-1]
        can_match = True
        for key, value in zip(o.keys, o.values):
            inner_type = self.get_mapping_item_type(o, current_type, key)
            if inner_type is None:
                can_match = False
                inner_type = self.chk.named_type("builtins.object")
            self.type_stack.append(inner_type)
            if self.visit(value) is None:
                can_match = False
            self.type_stack.pop()
        if can_match:
            return self.type_stack[-1]
        else:
            return None

    def get_mapping_item_type(self,
                              pattern: MappingPattern,
                              mapping_type: Type,
                              key_pattern: MappingKeyPattern
                              ) -> Optional[Type]:
        local_errors = self.msg.clean_copy()
        local_errors.disable_count = 0
        if isinstance(mapping_type, TypedDictType):
            result = self.chk.expr_checker.visit_typeddict_index_expr(mapping_type,
                                                                      key_pattern.expr,
                                                                      local_errors=local_errors
                                                                      )  # type: Optional[Type]
            # If we can't determine the type statically fall back to treating it as a normal
            # mapping
            if local_errors.is_errors():
                local_errors = self.msg.clean_copy()
                local_errors.disable_count = 0
                result = self.get_simple_mapping_item_type(pattern,
                                                           mapping_type,
                                                           key_pattern,
                                                           local_errors)

                if local_errors.is_errors():
                    result = None
        else:
            result = self.get_simple_mapping_item_type(pattern,
                                                       mapping_type,
                                                       key_pattern,
                                                       local_errors)
        return result

    def get_simple_mapping_item_type(self,
                                     pattern: MappingPattern,
                                     mapping_type: Type,
                                     key_pattern: MappingKeyPattern,
                                     local_errors: MessageBuilder
                                     ) -> Type:
        result, _ = self.chk.expr_checker.check_method_call_by_name('__getitem__',
                                                                    mapping_type,
                                                                    [key_pattern.expr],
                                                                    [ARG_POS],
                                                                    pattern,
                                                                    local_errors=local_errors)
        return result

    def visit_class_pattern(self, o: ClassPattern) -> Optional[Type]:
        current_type = self.type_stack[-1]
        class_name = o.class_ref.fullname
        assert class_name is not None
        sym = self.chk.lookup_qualified(class_name)
        if isinstance(sym.node, TypeAlias) and not sym.node.no_args:
            self.msg.fail("Class pattern class must not be a type alias with type parameters", o)
            return None
        if isinstance(sym.node, (TypeAlias, TypeInfo)):
            typ = self.chk.named_type(class_name)
        else:
            self.msg.fail('Class pattern must be a type. Found "{}"'.format(sym.type), o.class_ref)
            return None

        keyword_pairs = []  # type: List[Tuple[Optional[str], Pattern]]
        match_arg_names = []  # type: List[Optional[str]]

        can_match = True

        if self.should_self_match(typ):
            if len(o.positionals) >= 1:
                self.type_stack.append(typ)
                if self.visit(o.positionals[0]) is None:
                    can_match = False
                self.type_stack.pop()

                if len(o.positionals) > 1:
                    self.msg.fail("Too many positional patterns for class pattern", o)
                    self.type_stack.append(self.chk.named_type("builtins.object"))
                    for p in o.positionals[1:]:
                        if self.visit(p) is None:
                            can_match = False
                    self.type_stack.pop()
        else:
            match_args_type = find_member("__match_args__", typ, typ)

            if match_args_type is None and can_match:
                if len(o.positionals) >= 1:
                    self.msg.fail("Class doesn't define __match_args__", o)

            proper_match_args_type = get_proper_type(match_args_type)
            if isinstance(proper_match_args_type, TupleType):
                match_arg_names = get_match_arg_names(proper_match_args_type)

                if len(o.positionals) > len(match_arg_names):
                    self.msg.fail("Too many positional patterns for class pattern", o)
                    match_arg_names += [None] * (len(o.positionals) - len(match_arg_names))
            else:
                match_arg_names = [None] * len(o.positionals)

            positional_names = set()

            for arg_name, pos in zip(match_arg_names, o.positionals):
                keyword_pairs.append((arg_name, pos))
                positional_names.add(arg_name)

        keyword_names = set()
        for key, value in zip(o.keyword_keys, o.keyword_values):
            keyword_pairs.append((key, value))
            if key in match_arg_names:
                self.msg.fail('Keyword "{}" already matches a positional pattern'.format(key),
                              value)
            elif key in keyword_names:
                self.msg.fail('Duplicate keyword pattern "{}"'.format(key), value)
            keyword_names.add(key)

        for keyword, pattern in keyword_pairs:
            if keyword is not None:
                key_type = find_member(keyword, typ, current_type)
                if key_type is None:
                    key_type = self.chk.named_type("builtins.object")
            else:
                key_type = self.chk.named_type("builtins.object")

            self.type_stack.append(key_type)
            if self.visit(pattern) is None:
                can_match = False
            self.type_stack.pop()

        if can_match:
            return get_more_specific_type(current_type, typ)
        else:
            return None

    def should_self_match(self, typ: ProperType) -> bool:
        if isinstance(typ, Instance) and typ.type.is_named_tuple:
            return False
        for other in self.self_match_types:
            if is_subtype(typ, other):
                return True
        return False

    def generate_self_match_types(self) -> List[Type]:
        types = []  # type: List[Type]
        for name in self_match_type_names:
            try:
                types.append(self.chk.named_type(name))
            except KeyError:
                # Some built in types are not defined in all test cases
                pass

        return types


def get_match_arg_names(typ: TupleType) -> List[Optional[str]]:
    args = []  # type: List[Optional[str]]
    for item in typ.items:
        values = try_getting_str_literals_from_type(item)
        if values is None or len(values) != 1:
            args.append(None)
        else:
            args.append(values[0])
    return args


def get_more_specific_type(left: Optional[Type], right: Optional[Type]) -> Optional[Type]:
    if left is None or right is None:
        return None
    elif is_subtype(left, right):
        return left
    elif is_subtype(right, left):
        return right
    else:
        return None
