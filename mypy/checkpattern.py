"""Pattern checker. This file is conceptually part of TypeChecker."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Final, NamedTuple

from mypy import message_registry
from mypy.checker_shared import TypeCheckerSharedApi, TypeRange
from mypy.checkmember import analyze_member_access
from mypy.expandtype import expand_type_by_instance
from mypy.join import join_types
from mypy.literals import literal_hash
from mypy.maptype import map_instance_to_supertype
from mypy.meet import narrow_declared_type
from mypy.messages import MessageBuilder
from mypy.nodes import ARG_POS, Expression, NameExpr, TempNode, TypeAlias, Var
from mypy.options import Options
from mypy.patterns import (
    AsPattern,
    ClassPattern,
    MappingPattern,
    OrPattern,
    Pattern,
    SequencePattern,
    SingletonPattern,
    StarredPattern,
    ValuePattern,
)
from mypy.plugin import Plugin
from mypy.subtypes import is_same_type, is_subtype
from mypy.traverser import TraverserVisitor
from mypy.typeops import (
    coerce_to_literal,
    make_simplified_union,
    try_getting_str_literals_from_type,
    tuple_fallback,
)
from mypy.types import (
    AnyType,
    FunctionLike,
    Instance,
    NoneType,
    ProperType,
    TupleType,
    Type,
    TypeAliasType,
    TypedDictType,
    TypeOfAny,
    TypeType,
    TypeVarTupleType,
    TypeVarType,
    UninhabitedType,
    UnionType,
    UnpackType,
    callable_with_ellipsis,
    find_unpack_in_list,
    get_proper_type,
    split_with_prefix_and_suffix,
)
from mypy.typevars import fill_typevars, fill_typevars_with_any
from mypy.visitor import PatternVisitor

self_match_type_names: Final = [
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

non_sequence_match_type_names: Final = ["builtins.str", "builtins.bytes", "builtins.bytearray"]

# Repeated subtraction of product patterns can create exponentially many alternatives.
# Beyond this limit retain the original remainder, sacrificing precision, not soundness.
MAX_TUPLE_PATTERN_REST_ITEMS: Final = 1024


# For every Pattern a PatternType can be calculated. This requires recursively calculating
# the PatternTypes of the sub-patterns first.
# Using the data in the PatternType the match subject and captured names can be narrowed/inferred.
class PatternType(NamedTuple):
    type: Type  # The type the match subject can be narrowed to
    rest_type: Type  # The remaining type if the pattern didn't match
    captures: dict[NameExpr, Type]  # The variables captured by the pattern


class PatternChecker(PatternVisitor[PatternType]):
    """Pattern checker.

    This class checks if a pattern can match a type, what the type can be narrowed to, and what
    type capture patterns should be inferred as.
    """

    # Some services are provided by a TypeChecker instance.
    chk: TypeCheckerSharedApi
    # This is shared with TypeChecker, but stored also here for convenience.
    msg: MessageBuilder
    # Currently unused
    plugin: Plugin
    # The expression being matched against the pattern
    subject: Expression

    subject_type: Type
    # Type of the subject to check the (sub)pattern against
    type_context: list[Type]
    # Types that match against self instead of their __match_args__ if used as a class pattern
    # Filled in from self_match_type_names
    self_match_types: list[Type]
    # Types that are sequences, but don't match sequence patterns. Filled in from
    # non_sequence_match_type_names
    non_sequence_match_types: list[Type]

    options: Options

    def __init__(
        self, chk: TypeCheckerSharedApi, msg: MessageBuilder, plugin: Plugin, options: Options
    ) -> None:
        self.chk = chk
        self.msg = msg
        self.plugin = plugin

        self.type_context = []
        self.self_match_types = self.generate_types_from_names(self_match_type_names)
        self.non_sequence_match_types = self.generate_types_from_names(
            non_sequence_match_type_names
        )
        self.options = options
        self.or_bindings: dict[OrPattern, dict[str, NameExpr]] = {}
        self.reachable_patterns: set[Pattern] = set()
        self.intersection_errors: dict[Pattern, list[tuple[str, str]]] = {}

    def check_pattern(
        self, pattern: Pattern, typ: Type, bindings: dict[OrPattern, dict[str, NameExpr]]
    ) -> PatternType:
        """Analyze one case, combining reachability before reporting intersections."""
        self.or_bindings = bindings
        self.reachable_patterns.clear()
        self.intersection_errors.clear()
        result = self.accept(pattern, typ)
        for node, errors in self.intersection_errors.items():
            if node not in self.reachable_patterns:
                for types, reason in errors:
                    self.msg.impossible_intersection(types, reason, node)
        return result

    def accept(self, o: Pattern, type_context: Type) -> PatternType:
        self.type_context.append(type_context)
        result = o.accept(self)
        self.type_context.pop()
        if not is_uninhabited(result.type):
            self.reachable_patterns.add(o)
        return result

    def narrow_pattern(
        self, typ: Type, ranges: list[TypeRange], pattern: Pattern, *, default: Type
    ) -> tuple[Type, Type]:
        errors: list[tuple[str, str]] = []
        result = self.chk.conditional_types_with_intersection(
            typ, ranges, pattern, default=default, intersection_errors=errors
        )
        if errors:
            self.intersection_errors.setdefault(pattern, []).extend(errors)
        return result

    def visit_as_pattern(self, o: AsPattern) -> PatternType:
        current_type = self.type_context[-1]
        if o.pattern is not None:
            pattern_type = self.accept(o.pattern, current_type)
            typ, rest_type, type_map = pattern_type
        else:
            typ, rest_type, type_map = current_type, UninhabitedType(), {}

        if not is_uninhabited(typ) and o.name is not None:
            proper_type = get_proper_type(typ)
            if typ is current_type and isinstance(proper_type, UnionType):
                # This union already describes every captured value. Intersecting
                # each member with the entire union again adds no information.
                typ = make_simplified_union(proper_type.items)
            else:
                typ, _ = self.narrow_pattern(
                    current_type, [get_type_range(typ)], o, default=current_type
                )
            if not is_uninhabited(typ):
                type_map[o.name] = typ

        return PatternType(typ, rest_type, type_map)

    def visit_or_pattern(self, o: OrPattern) -> PatternType:
        current_type = self.type_context[-1]

        #
        # Check all the subpatterns
        #
        pattern_types = []
        for pattern in o.patterns:
            pattern_type = self.accept(pattern, current_type)
            pattern_types.append(pattern_type)
            if not is_uninhabited(pattern_type.type):
                current_type = pattern_type.rest_type

        #
        # Collect the final type
        #
        types = []
        for pattern_type in pattern_types:
            if not is_uninhabited(pattern_type.type):
                types.append(pattern_type.type)

        #
        # Check the capture types
        #
        capture_types: dict[Var, list[tuple[NameExpr, Type]]] = defaultdict(list)
        # Collect captures from the first subpattern
        for expr, typ in pattern_types[0].captures.items():
            node = get_var(expr)
            capture_types[node].append((expr, typ))

        # Syntax has already been validated. Reuse the same capture expressions
        # regardless of which alternative can match the current subject type.
        bindings = self.or_bindings[o]
        for pattern_type in pattern_types[1:]:
            for expr, typ in pattern_type.captures.items():
                node = get_var(expr)
                capture_types[node].append((expr, typ))

        captures: dict[NameExpr, Type] = {}
        for capture_list in capture_types.values():
            typ = UninhabitedType()
            for _, other in capture_list:
                typ = make_simplified_union([typ, other])

            capture = capture_list[0][0]
            # Imported aliases can have a different Var.name. The binding map
            # uses the name written in the pattern, not the declaration's name.
            captures[bindings[capture.name]] = typ

        union_type = make_simplified_union(types)
        return PatternType(union_type, current_type, captures)

    def visit_value_pattern(self, o: ValuePattern) -> PatternType:
        current_type = self.type_context[-1]
        typ = self.chk.expr_checker.accept(o.expr)
        typ = coerce_to_literal(typ)
        node = TempNode(current_type)
        # Value patterns are essentially a syntactic sugar on top of `if x == Value`.
        # They should be treated equivalently.
        ok_map, rest_map = self.chk.narrow_type_by_identity_equality(
            "==", [node, TempNode(typ)], [current_type, typ], [0, 1], {0}
        )
        ok_type = ok_map.get(node, current_type)
        rest_type = rest_map.get(node, current_type)
        return PatternType(ok_type, rest_type, {})

    def visit_singleton_pattern(self, o: SingletonPattern) -> PatternType:
        current_type = self.type_context[-1]
        value: bool | None = o.value
        if isinstance(value, bool):
            typ = self.chk.expr_checker.infer_literal_expr_type(value, "builtins.bool")
        elif value is None:
            typ = NoneType()
        else:
            assert False

        narrowed_type, rest_type = self.narrow_pattern(
            current_type, [get_type_range(typ)], o, default=current_type
        )
        return PatternType(narrowed_type, rest_type, {})

    def visit_sequence_pattern(self, o: SequencePattern) -> PatternType:
        #
        # Step 1. Check for existence of a starred pattern
        #
        current_type = get_proper_type(self.type_context[-1])
        if not self.can_match_sequence(current_type):
            return self.early_non_match()

        star_positions = [i for i, p in enumerate(o.patterns) if isinstance(p, StarredPattern)]
        star_position: int | None = None
        if len(star_positions) == 1:
            star_position = star_positions[0]
        elif len(star_positions) >= 2:
            assert False, "Parser should prevent multiple starred patterns"
        required_patterns = len(o.patterns)
        if star_position is not None:
            required_patterns -= 1

        #
        # Step 2. If we have a union, recurse and return the combined result
        #
        if isinstance(current_type, UnionType):
            match_types: list[Type] = []
            rest_types: list[Type] = []
            captures_list: dict[NameExpr, list[Type]] = {}

            if star_position is not None:
                star_pattern = o.patterns[star_position]
                assert isinstance(star_pattern, StarredPattern)
                star_expr = star_pattern.capture
            else:
                star_expr = None

            for t in current_type.items:
                match_type, rest_type, captures = self.accept(o, t)
                match_types.append(match_type)
                rest_types.append(rest_type)
                if not is_uninhabited(match_type):
                    for expr, typ in captures.items():
                        p_typ = get_proper_type(typ)
                        if expr not in captures_list:
                            captures_list[expr] = []
                        # Avoid adding in a list[Never] for empty list captures
                        if (
                            expr == star_expr
                            and isinstance(p_typ, Instance)
                            and p_typ.type.fullname == "builtins.list"
                            and is_uninhabited(p_typ.args[0])
                        ):
                            continue
                        captures_list[expr].append(typ)

            return PatternType(
                make_simplified_union(match_types),
                self.combine_tuple_remainders(rest_types, current_type),
                {expr: make_simplified_union(types) for expr, types in captures_list.items()},
            )

        #
        # Step 3. Get inner types of original type
        #
        unpack_index = None
        if isinstance(current_type, TupleType):
            inner_types: list[Type] = current_type.items
            unpack_index = find_unpack_in_list(inner_types)
            if unpack_index is None:
                size_diff = len(inner_types) - required_patterns
                if size_diff < 0:
                    return self.early_non_match()
                elif size_diff > 0 and star_position is None:
                    return self.early_non_match()
            else:
                normalized_inner_types = []
                for it in inner_types:
                    # Unfortunately, it is not possible to "split" the TypeVarTuple
                    # into individual items, so we just use its upper bound for the whole
                    # analysis instead.
                    if isinstance(it, UnpackType) and isinstance(it.type, TypeVarTupleType):
                        it = UnpackType(it.type.upper_bound)
                    normalized_inner_types.append(it)
                inner_types = normalized_inner_types
                current_type = current_type.copy_modified(items=normalized_inner_types)
                if len(inner_types) - 1 > required_patterns and star_position is None:
                    return self.early_non_match()
        elif isinstance(current_type, AnyType):
            inner_type = AnyType(TypeOfAny.from_another_any, current_type)
            inner_types = [inner_type] * len(o.patterns)
        elif isinstance(current_type, Instance) and self.chk.type_is_iterable(current_type):
            inner_type = self.chk.iterable_item_type(current_type, o)
            inner_types = [inner_type] * len(o.patterns)
        else:
            inner_type = self.chk.named_type("builtins.object")
            inner_types = [inner_type] * len(o.patterns)

        #
        # Step 4. Match inner patterns
        #
        contracted_new_inner_types: list[Type] = []
        contracted_rest_inner_types: list[Type] = []
        captures = {}

        contracted_inner_types = self.contract_starred_pattern_types(
            inner_types, star_position, required_patterns
        )
        for p, t in zip(o.patterns, contracted_inner_types):
            pattern_type = self.accept(p, t)
            typ, rest, type_map = pattern_type
            contracted_new_inner_types.append(typ)
            contracted_rest_inner_types.append(rest)
            self.update_type_map(captures, type_map)

        new_inner_types = self.expand_starred_pattern_types(
            contracted_new_inner_types, star_position, len(inner_types), unpack_index is not None
        )
        rest_inner_types = self.expand_starred_pattern_types(
            contracted_rest_inner_types, star_position, len(inner_types), unpack_index is not None
        )

        #
        # Step 5. Calculate new type
        #
        new_type: Type
        rest_type = current_type
        if isinstance(current_type, TupleType) and unpack_index is None:
            if any(is_uninhabited(typ) for typ in new_inner_types):
                new_type = UninhabitedType()
            else:
                new_type = TupleType(new_inner_types, current_type.partial_fallback)

                # A tuple fails to match at its first failing position. Preserve the
                # matched prefix and the original suffix in each remaining alternative:
                # (A, B) - (a, b) = (A - a, B) | (a, B - b).
                # Irrefutable subpatterns (including starred captures) keep their types.
                matched_types = [
                    curr if is_uninhabited(rest) else new
                    for curr, new, rest in zip(inner_types, new_inner_types, rest_inner_types)
                ]
                rest_items: list[Type] = []
                for i, rest in enumerate(rest_inner_types):
                    if is_uninhabited(rest):
                        continue
                    rest_item = TupleType(
                        matched_types[:i] + [rest] + inner_types[i + 1 :],
                        current_type.partial_fallback,
                    )
                    # Some complements cannot be expressed (e.g. int minus Literal[1]).
                    # Avoid redundant expansion when one alternative is already the
                    # entire original tuple, including when it contains Any.
                    if is_same_type(rest_item, current_type):
                        rest_items = [current_type]
                        break
                    rest_items.append(rest_item)
                    if len(rest_items) > MAX_TUPLE_PATTERN_REST_ITEMS:
                        break
                rest_type = self.combine_tuple_remainders(rest_items, current_type)
        elif isinstance(current_type, TupleType):
            # For variadic tuples it is too tricky to match individual items like for fixed
            # tuples, so we instead try to narrow the entire type.
            # TODO: use more precise narrowing when possible (e.g. for identical shapes).
            new_tuple_type = TupleType(new_inner_types, current_type.partial_fallback)
            new_type, _ = self.narrow_pattern(
                new_tuple_type, [get_type_range(current_type)], o, default=new_tuple_type
            )
            if (
                star_position is not None
                and required_patterns <= len(inner_types) - 1
                and all(is_uninhabited(rest) for rest in rest_inner_types)
            ):
                rest_type = UninhabitedType()
        else:
            new_inner_type = UninhabitedType()
            for typ in new_inner_types:
                new_inner_type = join_types(new_inner_type, typ)
            new_type = self.construct_sequence_child(current_type, new_inner_type)
            new_type, possible_rest_type = self.narrow_pattern(
                current_type, [get_type_range(new_type)], o, default=current_type
            )
            if star_position is not None and len(o.patterns) == 1:
                # Match cannot be refuted, so narrow the remaining type
                rest_type = possible_rest_type

        return PatternType(new_type, rest_type, captures)

    def combine_tuple_remainders(self, items: list[Type], original: Type) -> Type:
        proper_original = get_proper_type(original)
        # Bound expansion, not narrowing of a union already supplied by the user.
        limit = MAX_TUPLE_PATTERN_REST_ITEMS
        if isinstance(proper_original, UnionType):
            limit = max(limit, len(proper_original.items))
        # Counting only top-level alternatives misses expansion inside nested products.
        memo: dict[int, tuple[Type, int]] = {}
        complexity_limit = max(
            MAX_TUPLE_PATTERN_REST_ITEMS, tuple_pattern_complexity(original, memo)
        )
        complexity = 0
        flattened: list[Type] = []
        for item in items:
            complexity += tuple_pattern_complexity(item, memo, complexity_limit - complexity)
            if complexity > complexity_limit:
                return original
            proper_item = get_proper_type(item)
            if isinstance(proper_item, UnionType):
                flattened.extend(proper_item.items)
            elif not is_uninhabited(proper_item):
                flattened.append(item)
            if len(flattened) > limit:
                return original
        result = make_simplified_union(flattened)
        if tuple_pattern_complexity(result, memo, complexity_limit) > complexity_limit:
            return original
        return result

    def contract_starred_pattern_types(
        self, types: list[Type], star_pos: int | None, num_required_patterns: int
    ) -> list[Type]:
        """
        Contracts a list of types in a sequence pattern depending on the position of a starred
        capture pattern.

        For example if the sequence pattern [a, *b, c] is matched against types [bool, int, str,
        bytes] the contracted types are [bool, Union[int, str], bytes].

        If star_pos in None the types are returned unchanged.
        """
        unpack_index = find_unpack_in_list(types)
        if unpack_index is not None:
            # Variadic tuples require "re-shaping" to match the requested pattern.
            unpack = types[unpack_index]
            assert isinstance(unpack, UnpackType)
            unpacked = get_proper_type(unpack.type)
            # This should be guaranteed by the normalization in the caller.
            assert isinstance(unpacked, Instance) and unpacked.type.fullname == "builtins.tuple"
            if star_pos is None:
                missing = num_required_patterns - len(types) + 1
                new_types = types[:unpack_index]
                new_types += [unpacked.args[0]] * missing
                new_types += types[unpack_index + 1 :]
                return new_types
            prefix, middle, suffix = split_with_prefix_and_suffix(
                tuple(types), star_pos, num_required_patterns - star_pos
            )
            new_middle = []
            for m in middle:
                # The existing code expects the star item type, rather than the type of
                # the whole tuple "slice".
                if isinstance(m, UnpackType):
                    new_middle.append(unpacked.args[0])
                else:
                    new_middle.append(m)
            return list(prefix) + [make_simplified_union(new_middle)] + list(suffix)
        else:
            if star_pos is None:
                return types
            new_types = types[:star_pos]
            star_length = len(types) - num_required_patterns
            new_types.append(make_simplified_union(types[star_pos : star_pos + star_length]))
            new_types += types[star_pos + star_length :]
            return new_types

    def expand_starred_pattern_types(
        self, types: list[Type], star_pos: int | None, num_types: int, original_unpack: bool
    ) -> list[Type]:
        """Undoes the contraction done by contract_starred_pattern_types.

        For example if the sequence pattern is [a, *b, c] and types [bool, int, str] are extended
        to length 4 the result is [bool, int, int, str].
        """
        if star_pos is None:
            return types
        if original_unpack:
            # In the case where original tuple type has an unpack item, it is not practical
            # to coerce pattern type back to the original shape (and may not even be possible),
            # so we only restore the type of the star item.
            res = []
            for i, t in enumerate(types):
                if i != star_pos or is_uninhabited(t):
                    res.append(t)
                else:
                    res.append(UnpackType(self.chk.named_generic_type("builtins.tuple", [t])))
            return res
        new_types = types[:star_pos]
        star_length = num_types - len(types) + 1
        new_types += [types[star_pos]] * star_length
        new_types += types[star_pos + 1 :]

        return new_types

    def visit_starred_pattern(self, o: StarredPattern) -> PatternType:
        captures: dict[NameExpr, Type] = {}
        if o.capture is not None:
            list_type = self.chk.named_generic_type("builtins.list", [self.type_context[-1]])
            captures[o.capture] = list_type
        return PatternType(self.type_context[-1], UninhabitedType(), captures)

    def visit_mapping_pattern(self, o: MappingPattern) -> PatternType:
        current_type = get_proper_type(self.type_context[-1])
        can_match = True
        captures: dict[NameExpr, Type] = {}
        for key, value in zip(o.keys, o.values):
            inner_type = self.get_mapping_item_type(o, current_type, key)
            if inner_type is None:
                can_match = False
                inner_type = self.chk.named_type("builtins.object")
            pattern_type = self.accept(value, inner_type)
            if is_uninhabited(pattern_type.type):
                can_match = False
            else:
                self.update_type_map(captures, pattern_type.captures)

        if o.rest is not None:
            mapping = self.chk.named_type("typing.Mapping")
            if is_subtype(current_type, mapping) and isinstance(current_type, Instance):
                mapping_inst = map_instance_to_supertype(current_type, mapping.type)
                dict_typeinfo = self.chk.lookup_typeinfo("builtins.dict")
                rest_type = Instance(dict_typeinfo, mapping_inst.args)
            else:
                object_type = self.chk.named_type("builtins.object")
                rest_type = self.chk.named_generic_type(
                    "builtins.dict", [object_type, object_type]
                )

            captures[o.rest] = rest_type

        else_type = current_type
        if can_match:
            # We can't narrow the type here, as Mapping key is invariant.
            new_type = self.type_context[-1]
            if not o.keys:
                # Match cannot be refuted, so narrow the remaining type
                mapping = self.chk.named_type("typing.Mapping")
                if_type, else_type = self.narrow_pattern(
                    current_type,
                    [TypeRange(mapping, is_upper_bound=False)],
                    o,
                    default=current_type,
                )
                if not isinstance(current_type, AnyType):
                    new_type = if_type
        else:
            new_type = UninhabitedType()
        return PatternType(new_type, else_type, captures)

    def get_mapping_item_type(
        self, pattern: MappingPattern, mapping_type: Type, key: Expression
    ) -> Type | None:
        mapping_type = get_proper_type(mapping_type)
        if isinstance(mapping_type, TypedDictType):
            with self.msg.filter_errors() as local_errors:
                result: Type | None = self.chk.expr_checker.visit_typeddict_index_expr(
                    mapping_type, key
                )[0]
                has_local_errors = local_errors.has_new_errors()
            # If we can't determine the type statically fall back to treating it as a normal
            # mapping
            if has_local_errors:
                with self.msg.filter_errors() as local_errors:
                    result = self.get_simple_mapping_item_type(pattern, mapping_type, key)

                    if local_errors.has_new_errors():
                        result = None
        else:
            with self.msg.filter_errors():
                result = self.get_simple_mapping_item_type(pattern, mapping_type, key)
        return result

    def get_simple_mapping_item_type(
        self, pattern: MappingPattern, mapping_type: Type, key: Expression
    ) -> Type:
        result, _ = self.chk.expr_checker.check_method_call_by_name(
            "__getitem__", mapping_type, [key], [ARG_POS], pattern
        )
        return result

    def visit_class_pattern(self, o: ClassPattern) -> PatternType:
        current_type = get_proper_type(self.type_context[-1])

        #
        # Check class type
        #
        type_info = o.class_ref.node
        if isinstance(type_info, TypeAlias) and not type_info.no_args:
            self.msg.fail(message_registry.CLASS_PATTERN_GENERIC_TYPE_ALIAS, o)
            return self.early_non_match()

        typ = self.chk.expr_checker.accept(o.class_ref)
        type_ranges = self.get_class_pattern_type_ranges(typ, o)
        if type_ranges is None:
            return self.early_non_match()
        typ = UnionType.make_union([t.item for t in type_ranges])

        new_type, rest_type = self.narrow_pattern(
            current_type, type_ranges, o, default=current_type
        )
        if is_uninhabited(new_type):
            return self.early_non_match()
        # TODO: Do I need this?
        narrowed_type = narrow_declared_type(current_type, new_type)

        #
        # Convert positional to keyword patterns
        #
        keyword_pairs: list[tuple[str | None, Pattern]] = []
        match_arg_set: set[str] = set()

        captures: dict[NameExpr, Type] = {}

        if len(o.positionals) != 0:
            if self.should_self_match(typ):
                if len(o.positionals) > 1:
                    self.msg.fail(message_registry.CLASS_PATTERN_TOO_MANY_POSITIONAL_ARGS, o)
                pattern_type = self.accept(o.positionals[0], narrowed_type)
                if not is_uninhabited(pattern_type.type):
                    return PatternType(
                        pattern_type.type,
                        make_simplified_union([rest_type, pattern_type.rest_type]),
                        pattern_type.captures,
                    )
                captures = pattern_type.captures
            else:
                with self.msg.filter_errors() as local_errors:
                    match_args_type = analyze_member_access(
                        "__match_args__",
                        typ,
                        o,
                        is_lvalue=False,
                        is_super=False,
                        is_operator=False,
                        original_type=typ,
                        chk=self.chk,
                    )
                    has_local_errors = local_errors.has_new_errors()
                if has_local_errors:
                    self.msg.fail(
                        message_registry.MISSING_MATCH_ARGS.format(
                            typ.str_with_options(self.options)
                        ),
                        o,
                    )
                    return self.early_non_match()

                proper_match_args_type = get_proper_type(match_args_type)
                if isinstance(proper_match_args_type, TupleType):
                    match_arg_names = get_match_arg_names(proper_match_args_type)

                    if len(o.positionals) > len(match_arg_names):
                        self.msg.fail(message_registry.CLASS_PATTERN_TOO_MANY_POSITIONAL_ARGS, o)
                        return self.early_non_match()
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
                self.msg.fail(
                    message_registry.CLASS_PATTERN_KEYWORD_MATCHES_POSITIONAL.format(key), value
                )
                has_duplicates = True
            elif key in keyword_arg_set:
                self.msg.fail(
                    message_registry.CLASS_PATTERN_DUPLICATE_KEYWORD_PATTERN.format(key), value
                )
                has_duplicates = True
            keyword_arg_set.add(key)

        if has_duplicates:
            return self.early_non_match()

        #
        # Check keyword patterns
        #
        can_match = True
        for keyword, pattern in keyword_pairs:
            key_type: Type | None = None
            with self.msg.filter_errors() as local_errors:
                if keyword is not None:
                    key_type = analyze_member_access(
                        keyword,
                        narrowed_type,
                        pattern,
                        is_lvalue=False,
                        is_super=False,
                        is_operator=False,
                        original_type=new_type,
                        chk=self.chk,
                    )
                else:
                    key_type = AnyType(TypeOfAny.from_error)
                has_local_errors = local_errors.has_new_errors()
            if has_local_errors or key_type is None:
                key_type = AnyType(TypeOfAny.from_error)
                if not (type_info and type_info.fullname == "builtins.object"):
                    self.msg.fail(
                        message_registry.CLASS_PATTERN_UNKNOWN_KEYWORD.format(
                            typ.str_with_options(self.options), keyword
                        ),
                        pattern,
                    )
                elif keyword is not None:
                    new_type = self.chk.add_any_attribute_to_type(new_type, keyword)

            inner_type, inner_rest_type, inner_captures = self.accept(pattern, key_type)
            if is_uninhabited(inner_type):
                can_match = False
            else:
                self.update_type_map(captures, inner_captures)
                if not is_uninhabited(inner_rest_type):
                    rest_type = current_type

        if not can_match:
            new_type = UninhabitedType()
        return PatternType(new_type, rest_type, captures)

    def get_class_pattern_type_ranges(self, typ: Type, o: ClassPattern) -> list[TypeRange] | None:
        p_typ = get_proper_type(typ)

        if isinstance(p_typ, UnionType):
            type_ranges = []
            for item in p_typ.items:
                type_range = self.get_class_pattern_type_ranges(item, o)
                if type_range is not None:
                    type_ranges.extend(type_range)
            if not type_ranges:
                return None
            return type_ranges

        if isinstance(p_typ, FunctionLike) and p_typ.is_type_obj():
            typ = fill_typevars_with_any(p_typ.type_object())
            return [TypeRange(typ, is_upper_bound=False)]
        if (
            isinstance(o.class_ref.node, Var)
            and o.class_ref.node.type is not None
            and o.class_ref.node.fullname == "typing.Callable"
        ):
            # Create a `Callable[..., Any]`
            fallback = self.chk.named_type("builtins.function")
            any_type = AnyType(TypeOfAny.unannotated)
            typ = callable_with_ellipsis(any_type, ret_type=any_type, fallback=fallback)
            return [TypeRange(typ, is_upper_bound=False)]
        if isinstance(p_typ, TypeType):
            typ = p_typ.item
            return [TypeRange(p_typ.item, is_upper_bound=True)]
        if isinstance(p_typ, AnyType):
            return [TypeRange(p_typ, is_upper_bound=False)]

        self.msg.fail(
            message_registry.CLASS_PATTERN_TYPE_REQUIRED.format(
                typ.str_with_options(self.options)
            ),
            o,
        )
        return None

    def should_self_match(self, typ: Type) -> bool:
        typ = get_proper_type(typ)
        if isinstance(typ, TupleType):
            typ = typ.partial_fallback
        if isinstance(typ, AnyType):
            return False
        if isinstance(typ, Instance) and typ.type.get("__match_args__") is not None:
            # Named tuples and other subtypes of builtins that define __match_args__
            # should not self match.
            return False
        for other in self.self_match_types:
            if is_subtype(typ, other):
                return True
        return False

    def can_match_sequence(self, typ: ProperType) -> bool:
        if isinstance(typ, AnyType):
            return True
        if isinstance(typ, UnionType):
            return any(self.can_match_sequence(get_proper_type(item)) for item in typ.items)
        for other in self.non_sequence_match_types:
            # We have to ignore promotions, as memoryview should match, but bytes,
            # which it can be promoted to, shouldn't
            if is_subtype(typ, other, ignore_promotions=True):
                return False
        sequence = self.chk.named_type("typing.Sequence")
        # If the static type is more general than sequence the actual type could still match
        return is_subtype(typ, sequence) or is_subtype(sequence, typ)

    def generate_types_from_names(self, type_names: list[str]) -> list[Type]:
        types: list[Type] = []
        for name in type_names:
            try:
                types.append(self.chk.named_type(name))
            except KeyError as e:
                # Some built in types are not defined in all test cases
                if not name.startswith("builtins."):
                    raise e
        return types

    def update_type_map(
        self, original_type_map: dict[NameExpr, Type], extra_type_map: dict[NameExpr, Type]
    ) -> None:
        # Calculating this would not be needed if TypeMap directly used literal hashes instead of
        # expressions, as suggested in the TODO above it's definition
        already_captured = {literal_hash(expr) for expr in original_type_map}
        for expr, typ in extra_type_map.items():
            if literal_hash(expr) in already_captured:
                node = get_var(expr)
                self.msg.fail(
                    message_registry.MULTIPLE_ASSIGNMENTS_IN_PATTERN.format(node.name), expr
                )
            else:
                original_type_map[expr] = typ

    def construct_sequence_child(self, outer_type: Type, inner_type: Type) -> Type:
        """
        If outer_type is a child class of typing.Sequence returns a new instance of
        outer_type, that is a Sequence of inner_type. If outer_type is not a child class of
        typing.Sequence just returns a Sequence of inner_type

        For example:
        construct_sequence_child(List[int], str) = List[str]

        TODO: this doesn't make sense. For example if one has class S(Sequence[int], Generic[T])
        or class T(Sequence[Tuple[T, T]]), there is no way any of those can map to Sequence[str].
        """
        proper_type = get_proper_type(outer_type)
        if isinstance(proper_type, TypeVarType):
            new_bound = self.construct_sequence_child(proper_type.upper_bound, inner_type)
            return proper_type.copy_modified(upper_bound=new_bound)
        if isinstance(proper_type, AnyType):
            return outer_type
        if isinstance(proper_type, UnionType):
            types = [
                self.construct_sequence_child(item, inner_type)
                for item in proper_type.items
                if self.can_match_sequence(get_proper_type(item))
            ]
            return make_simplified_union(types)
        sequence = self.chk.named_generic_type("typing.Sequence", [inner_type])
        if is_subtype(outer_type, self.chk.named_type("typing.Sequence")):
            if isinstance(proper_type, TupleType):
                proper_type = tuple_fallback(proper_type)
            assert isinstance(proper_type, Instance)
            empty_type = fill_typevars(proper_type.type)
            partial_type = expand_type_by_instance(empty_type, sequence)
            return expand_type_by_instance(partial_type, proper_type)
        else:
            return sequence

    def early_non_match(self) -> PatternType:
        return PatternType(UninhabitedType(), self.type_context[-1], {})


class PatternBindingCollector(TraverserVisitor):
    def __init__(
        self, msg: MessageBuilder, or_bindings: dict[OrPattern, dict[str, NameExpr]]
    ) -> None:
        self.bindings: dict[str, NameExpr] = {}
        self.msg = msg
        self.or_bindings = or_bindings

    def visit_or_pattern(self, o: OrPattern) -> None:
        first: dict[str, NameExpr] | None = None
        canonical: dict[str, NameExpr] = {}
        for i, pattern in enumerate(o.patterns):
            collector = PatternBindingCollector(self.msg, self.or_bindings)
            pattern.accept(collector)
            bindings = collector.bindings
            if first is None:
                first = bindings
            elif first.keys() != bindings.keys():
                # Invalid nested alternatives must be diagnosed even when type
                # matching cannot reach them (e.g. inside a wrong-length tuple).
                self.msg.fail(message_registry.OR_PATTERN_ALTERNATIVE_NAMES, o.patterns[i - 1])
            for name, expr in bindings.items():
                canonical.setdefault(name, expr)
        self.or_bindings[o] = canonical
        for name, expr in canonical.items():
            self.bindings.setdefault(name, expr)

    def visit_as_pattern(self, o: AsPattern) -> None:
        if o.name is not None:
            self.bindings.setdefault(o.name.name, o.name)
        super().visit_as_pattern(o)

    def visit_starred_pattern(self, o: StarredPattern) -> None:
        if o.capture is not None:
            self.bindings.setdefault(o.capture.name, o.capture)
        super().visit_starred_pattern(o)

    def visit_mapping_pattern(self, o: MappingPattern) -> None:
        if o.rest is not None:
            self.bindings.setdefault(o.rest.name, o.rest)
        super().visit_mapping_pattern(o)


def analyze_pattern_bindings(
    patterns: Sequence[Pattern], msg: MessageBuilder
) -> dict[OrPattern, dict[str, NameExpr]]:
    """Validate OR bindings once, independently of type-based pattern reachability."""
    bindings: dict[OrPattern, dict[str, NameExpr]] = {}
    collector = PatternBindingCollector(msg, bindings)
    for pattern in patterns:
        pattern.accept(collector)
    return bindings


def tuple_pattern_complexity(
    typ: Type, memo: dict[int, tuple[Type, int]], limit: int | None = None
) -> int:
    """Count represented tuple occurrences without unfolding recursive definitions."""
    if cached := memo.get(id(typ)):
        return cached[1]
    if isinstance(typ, TypeAliasType) and typ.is_recursive:
        children = typ.args
        count = 0
    else:
        proper_type = get_proper_type(typ)
        children = proper_type.items if isinstance(proper_type, (TupleType, UnionType)) else []
        count = int(isinstance(proper_type, TupleType))
    for child in children:
        count += tuple_pattern_complexity(child, memo, None if limit is None else limit - count)
        if limit is not None and count > limit:
            return limit + 1
    # Keep the object alive: expanding an alias may allocate temporary types, whose
    # identities must not be reused while this memo is in use. Count each occurrence
    # separately even when two positions refer to the same object.
    memo[id(typ)] = (typ, count)
    return count


def get_match_arg_names(typ: TupleType) -> list[str | None]:
    args: list[str | None] = []
    for item in typ.items:
        values = try_getting_str_literals_from_type(item)
        if values is None or len(values) != 1:
            args.append(None)
        else:
            args.append(values[0])
    return args


def get_var(expr: NameExpr) -> Var:
    """
    Warning: this in only true for expressions captured by a match statement.
    Don't call it from anywhere else
    """
    node = expr.node
    assert isinstance(node, Var), node
    return node


def get_type_range(typ: Type) -> TypeRange:
    typ = get_proper_type(typ)
    if (
        isinstance(typ, Instance)
        and typ.last_known_value
        and isinstance(typ.last_known_value.value, bool)
    ):
        typ = typ.last_known_value
    return TypeRange(typ, is_upper_bound=False)


def is_uninhabited(typ: Type) -> bool:
    return isinstance(get_proper_type(typ), UninhabitedType)
