"""Pattern checker. This file is conceptually part of TypeChecker."""
from typing import List, Optional, Union, Tuple, Dict, NamedTuple, Set

import mypy.checker
from mypy.expandtype import expand_type_by_instance
from mypy.join import join_types
from mypy.literals import literal_hash
from mypy.messages import MessageBuilder
from mypy.nodes import Expression, ARG_POS, TypeAlias, TypeInfo, Var, NameExpr
from mypy.patterns import (
    Pattern, AsPattern, OrPattern, LiteralPattern, CapturePattern, WildcardPattern, ValuePattern,
    SequencePattern, StarredPattern, MappingPattern, ClassPattern, MappingKeyPattern
)
from mypy.plugin import Plugin
from mypy.subtypes import is_subtype, find_member
from mypy.typeops import try_getting_str_literals_from_type
from mypy.types import (
    ProperType, AnyType, TypeOfAny, Instance, Type, NoneType, UninhabitedType, get_proper_type,
    TypedDictType, TupleType
)
from mypy.typevars import fill_typevars
from mypy.visitor import PatternVisitor

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


PatternType = NamedTuple(
    'PatternType',
    [
        ('type', Optional[Type]),
        ('captures', Dict[Expression, Type]),
    ])


class PatternChecker(PatternVisitor[PatternType]):
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

    subject_type = None  # type: Type
    # Type of the subject to check the (sub)pattern against
    type_context = None  # type: List[Type]

    self_match_types = None  # type: List[Type]

    def __init__(self,
                 chk: 'mypy.checker.TypeChecker',
                 msg: MessageBuilder, plugin: Plugin
                 ) -> None:
        self.chk = chk
        self.msg = msg
        self.plugin = plugin

        self.type_context = []
        self.self_match_types = self.generate_self_match_types()

    def accept(self, o: Pattern, type_context: Type) -> PatternType:
        self.type_context.append(type_context)
        result = o.accept(self)
        self.type_context.pop()

        return result

    def visit_as_pattern(self, o: AsPattern) -> PatternType:
        pattern_type = self.accept(o.pattern, self.type_context[-1])
        typ, type_map = pattern_type
        if typ is None:
            return pattern_type
        as_pattern_type = self.accept(o.name, typ)
        self.update_type_map(type_map, as_pattern_type.captures)
        return PatternType(typ, type_map)

    def visit_or_pattern(self, o: OrPattern) -> PatternType:
        # TODO
        return PatternType(self.type_context[-1], {})

    def visit_literal_pattern(self, o: LiteralPattern) -> PatternType:
        literal_type = self.get_literal_type(o.value)
        typ = get_more_specific_type(literal_type, self.type_context[-1])
        return PatternType(typ, {})

    def get_literal_type(self, l: Union[int, complex, float, str, bytes, None]) -> Type:
        if l is None:
            typ = NoneType()  # type: Type
        elif isinstance(l, int):
            typ = self.chk.named_type("builtins.int")
        elif isinstance(l, complex):
            typ = self.chk.named_type("builtins.complex")
        elif isinstance(l, float):
            typ = self.chk.named_type("builtins.float")
        elif isinstance(l, str):
            typ = self.chk.named_type("builtins.str")
        elif isinstance(l, bytes):
            typ = self.chk.named_type("builtins.bytes")
        elif isinstance(l, bool):
            typ = self.chk.named_type("builtins.bool")
        else:
            assert False, "Invalid literal in literal pattern"

        return typ

    def visit_capture_pattern(self, o: CapturePattern) -> PatternType:
        node = o.name.node
        assert isinstance(node, Var)
        return PatternType(self.type_context[-1], {o.name: self.type_context[-1]})

    def visit_wildcard_pattern(self, o: WildcardPattern) -> PatternType:
        return PatternType(self.type_context[-1], {})

    def visit_value_pattern(self, o: ValuePattern) -> PatternType:
        typ = self.chk.expr_checker.accept(o.expr)
        specific_typ = get_more_specific_type(typ, self.type_context[-1])
        return PatternType(specific_typ, {})

    def visit_sequence_pattern(self, o: SequencePattern) -> PatternType:
        current_type = self.type_context[-1]
        inner_type = self.get_sequence_type(current_type)
        if inner_type is None:
            if is_subtype(self.chk.named_type("typing.Iterable"), current_type):
                # Current type is more general, but the actual value could still be iterable
                inner_type = self.chk.named_type("builtins.object")
            else:
                return early_non_match()

        new_inner_type = UninhabitedType()  # type: Type
        captures = {}  # type: Dict[Expression, Type]
        can_match = True
        for p in o.patterns:
            pattern_type = self.accept(p, inner_type)
            typ, type_map = pattern_type
            if typ is None:
                can_match = False
            else:
                new_inner_type = join_types(new_inner_type, typ)
            self.update_type_map(captures, type_map)

        new_type = None  # type: Optional[Type]
        if can_match:
            new_type = self.construct_iterable_child(current_type, new_inner_type)
            if not is_subtype(new_type, current_type):
                new_type = current_type
        return PatternType(new_type, captures)

    def get_sequence_type(self, t: Type) -> Optional[Type]:
        t = get_proper_type(t)
        if isinstance(t, AnyType):
            return AnyType(TypeOfAny.from_another_any, t)

        if self.chk.type_is_iterable(t) and isinstance(t, Instance):
            return self.chk.iterable_item_type(t)
        else:
            return None

    def visit_starred_pattern(self, o: StarredPattern) -> PatternType:
        if isinstance(o.capture, CapturePattern):
            list_type = self.chk.named_generic_type('builtins.list', [self.type_context[-1]])
            pattern_type = self.accept(o.capture, list_type)
            captures = pattern_type.captures
        elif isinstance(o.capture, WildcardPattern):
            captures = {}
        else:
            assert False
        return PatternType(self.type_context[-1], captures)

    def visit_mapping_pattern(self, o: MappingPattern) -> PatternType:
        current_type = self.type_context[-1]
        can_match = True
        captures = {}  # type: Dict[Expression, Type]
        for key, value in zip(o.keys, o.values):
            inner_type = self.get_mapping_item_type(o, current_type, key)
            if inner_type is None:
                can_match = False
                inner_type = self.chk.named_type("builtins.object")
            pattern_type = self.accept(value, inner_type)
            if pattern_type is None:
                can_match = False
            else:
                self.update_type_map(captures, pattern_type.captures)
        if can_match:
            new_type = self.type_context[-1]  # type: Optional[Type]
        else:
            new_type = None
        return PatternType(new_type, captures)

    def get_mapping_item_type(self,
                              pattern: MappingPattern,
                              mapping_type: Type,
                              key_pattern: MappingKeyPattern
                              ) -> Optional[Type]:
        local_errors = self.msg.clean_copy()
        local_errors.disable_count = 0
        mapping_type = get_proper_type(mapping_type)
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

    def visit_class_pattern(self, o: ClassPattern) -> PatternType:
        current_type = self.type_context[-1]

        #
        # Check class type
        #
        class_name = o.class_ref.fullname
        assert class_name is not None
        sym = self.chk.lookup_qualified(class_name)
        if isinstance(sym.node, TypeAlias) and not sym.node.no_args:
            self.msg.fail("Class pattern class must not be a type alias with type parameters", o)
            return early_non_match()
        if isinstance(sym.node, (TypeAlias, TypeInfo)):
            typ = self.chk.named_type(class_name)
        else:
            self.msg.fail('Class pattern must be a type. Found "{}"'.format(sym.type), o.class_ref)
            return early_non_match()

        #
        # Convert positional to keyword patterns
        #
        keyword_pairs = []  # type: List[Tuple[Optional[str], Pattern]]
        match_arg_set = set()  # type: Set[str]

        captures = {}  # type: Dict[Expression, Type]

        if len(o.positionals) != 0:
            if self.should_self_match(typ):
                if len(o.positionals) > 1:
                    self.msg.fail("Too many positional patterns for class pattern", o)
                pattern_type = self.accept(o.positionals[0], typ)
                if pattern_type.type is None:
                    return pattern_type
                captures = pattern_type.captures
            else:
                match_args_type = find_member("__match_args__", typ, typ)

                if match_args_type is None:
                    self.msg.fail("Class doesn't define __match_args__", o)
                    return early_non_match()

                proper_match_args_type = get_proper_type(match_args_type)
                if isinstance(proper_match_args_type, TupleType):
                    match_arg_names = get_match_arg_names(proper_match_args_type)

                    if len(o.positionals) > len(match_arg_names):
                        self.msg.fail("Too many positional patterns for class pattern", o)
                        return early_non_match()
                else:
                    match_arg_names = [None] * len(o.positionals)

                for arg_name, pos in zip(match_arg_names, o.positionals):
                    keyword_pairs.append((arg_name, pos))
                    if arg_name is not None:
                        match_arg_set.add(arg_name)

        #
        # Check for duplicate patterns
        #
        keyword_arg_set = set()
        has_duplicates = False
        for key, value in zip(o.keyword_keys, o.keyword_values):
            keyword_pairs.append((key, value))
            if key in match_arg_set:
                self.msg.fail('Keyword "{}" already matches a positional pattern'.format(key),
                              value)
                has_duplicates = True
            elif key in keyword_arg_set:
                self.msg.fail('Duplicate keyword pattern "{}"'.format(key), value)
                has_duplicates = True
            keyword_arg_set.add(key)

        if has_duplicates:
            return early_non_match()

        #
        # Check keyword patterns
        #
        can_match = True
        for keyword, pattern in keyword_pairs:
            key_type = None  # type: Optional[Type]
            if keyword is not None:
                key_type = find_member(keyword, typ, current_type)
            if key_type is None:
                key_type = AnyType(TypeOfAny.implementation_artifact)

            pattern_type = self.accept(pattern, key_type)
            if pattern_type is None:
                can_match = False
            else:
                self.update_type_map(captures, pattern_type.captures)

        if can_match:
            new_type = get_more_specific_type(current_type, typ)
        else:
            new_type = None
        return PatternType(new_type, captures)

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

    def update_type_map(self,
                        original_type_map: Dict[Expression, Type],
                        extra_type_map: Dict[Expression, Type]
                        ) -> None:
        # Calculating this would not be needed if TypeMap directly used literal hashes instead of
        # expressions, as suggested in the TODO above it's definition
        already_captured = set(literal_hash(expr) for expr in original_type_map)
        for expr, typ in extra_type_map.items():
            if literal_hash(expr) in already_captured:
                assert isinstance(expr, NameExpr)
                node = expr.node
                assert node is not None
                self.msg.fail('Multiple assignments to name "{}" in pattern'.format(node.name),
                              expr)
            else:
                original_type_map[expr] = typ

    def construct_iterable_child(self, outer_type: Type, inner_type: Type) -> Type:
        iterable = self.chk.named_generic_type("typing.Iterable", [inner_type])
        if self.chk.type_is_iterable(outer_type):
            proper_type = get_proper_type(outer_type)
            assert isinstance(proper_type, Instance)
            empty_type = fill_typevars(proper_type.type)
            partial_type = expand_type_by_instance(empty_type, iterable)
            return expand_type_by_instance(partial_type, proper_type)
        else:
            return iterable


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


def early_non_match() -> PatternType:
    return PatternType(None, {})
