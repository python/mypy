from typing import (Any, Dict, List, Set, Iterator)
from contextlib import contextmanager

from mypy.types import Type, AnyType, PartialType
from mypy.nodes import (Node, Var)

from mypy.subtypes import is_subtype
from mypy.join import join_simple
from mypy.sametypes import is_same_type


class Frame(Dict[Any, Type]):
    pass


class Key(AnyType):
    pass


class ConditionalTypeBinder:
    """Keep track of conditional types of variables.

    NB: Variables are tracked by literal expression, so it is possible
    to confuse the binder; for example,

    ```
    class A:
        a = None          # type: Union[int, str]
    x = A()
    lst = [x]
    reveal_type(x.a)      # Union[int, str]
    x.a = 1
    reveal_type(x.a)      # int
    reveal_type(lst[0].a) # Union[int, str]
    lst[0].a = 'a'
    reveal_type(x.a)      # int
    reveal_type(lst[0].a) # str
    ```
    """

    def __init__(self) -> None:
        # The set of frames currently used.  These map
        # expr.literal_hash -- literals like 'foo.bar' --
        # to types.
        self.frames = [Frame()]

        # For frames higher in the stack, we record the set of
        # Frames that can escape there
        self.options_on_return = []  # type: List[List[Frame]]

        # Maps expr.literal_hash] to get_declaration(expr)
        # for every expr stored in the binder
        self.declarations = Frame()
        # Set of other keys to invalidate if a key is changed, e.g. x -> {x.a, x[0]}
        # Whenever a new key (e.g. x.a.b) is added, we update this
        self.dependencies = {}  # type: Dict[Key, Set[Key]]

        # breaking_out is set to True on return/break/continue/raise
        # It is cleared on pop_frame() and placed in last_pop_breaking_out
        # Lines of code after breaking_out = True are unreachable and not
        # typechecked.
        self.breaking_out = False

        # Whether the last pop changed the newly top frame on exit
        self.last_pop_changed = False
        # Whether the last pop was necessarily breaking out, and couldn't fall through
        self.last_pop_breaking_out = False

        self.try_frames = set()  # type: Set[int]
        self.loop_frames = []  # type: List[int]

    def _add_dependencies(self, key: Key, value: Key = None) -> None:
        if value is None:
            value = key
        else:
            self.dependencies.setdefault(key, set()).add(value)
        if isinstance(key, tuple):
            for elt in key:
                self._add_dependencies(elt, value)

    def push_frame(self) -> Frame:
        """Push a new frame into the binder."""
        f = Frame()
        self.frames.append(f)
        self.options_on_return.append([])
        return f

    def _push(self, key: Key, type: Type, index: int=-1) -> None:
        self.frames[index][key] = type

    def _get(self, key: Key, index: int=-1) -> Type:
        if index < 0:
            index += len(self.frames)
        for i in range(index, -1, -1):
            if key in self.frames[i]:
                return self.frames[i][key]
        return None

    def push(self, expr: Node, typ: Type) -> None:
        if not expr.literal:
            return
        key = expr.literal_hash
        if key not in self.declarations:
            self.declarations[key] = self.get_declaration(expr)
            self._add_dependencies(key)
        self._push(key, typ)

    def get(self, expr: Node) -> Type:
        return self._get(expr.literal_hash)

    def cleanse(self, expr: Node) -> None:
        """Remove all references to a Node from the binder."""
        self._cleanse_key(expr.literal_hash)

    def _cleanse_key(self, key: Key) -> None:
        """Remove all references to a key from the binder."""
        for frame in self.frames:
            if key in frame:
                del frame[key]

    def update_from_options(self, frames: List[Frame]) -> bool:
        """Update the frame to reflect that each key will be updated
        as in one of the frames.  Return whether any item changes.

        If a key is declared as AnyType, only update it if all the
        options are the same.
        """

        changed = False
        keys = set(key for f in frames for key in f)

        for key in keys:
            current_value = self._get(key)
            resulting_values = [f.get(key, current_value) for f in frames]
            if any(x is None for x in resulting_values):
                continue

            if isinstance(self.declarations.get(key), AnyType):
                type = resulting_values[0]
                if not all(is_same_type(type, t) for t in resulting_values[1:]):
                    type = AnyType()
            else:
                type = resulting_values[0]
                for other in resulting_values[1:]:
                    type = join_simple(self.declarations[key], type, other)
            if not is_same_type(type, current_value):
                self._push(key, type)
                changed = True

        return changed

    def pop_frame(self, fall_through: int = 0) -> Frame:
        """Pop a frame and return it.

        See frame_context() for documentation of fall_through.
        """
        if fall_through and not self.breaking_out:
            self.allow_jump(-fall_through)

        result = self.frames.pop()
        options = self.options_on_return.pop()

        self.last_pop_changed = self.update_from_options(options)
        self.last_pop_breaking_out = self.breaking_out

        return result

    def get_declaration(self, expr: Any) -> Type:
        if hasattr(expr, 'node') and isinstance(expr.node, Var):
            type = expr.node.type
            if isinstance(type, PartialType):
                return None
            return type
        else:
            return None

    def assign_type(self, expr: Node,
                    type: Type,
                    declared_type: Type,
                    restrict_any: bool = False) -> None:
        if not expr.literal:
            return
        self.invalidate_dependencies(expr)

        if declared_type is None:
            # Not sure why this happens.  It seems to mainly happen in
            # member initialization.
            return
        if not is_subtype(type, declared_type):
            # Pretty sure this is only happens when there's a type error.

            # Ideally this function wouldn't be called if the
            # expression has a type error, though -- do other kinds of
            # errors cause this function to get called at invalid
            # times?
            return

        # If x is Any and y is int, after x = y we do not infer that x is int.
        # This could be changed.
        # Eric: I'm changing it in weak typing mode, since Any is so common.

        if (isinstance(self.most_recent_enclosing_type(expr, type), AnyType)
                and not restrict_any):
            pass
        elif isinstance(type, AnyType):
            self.push(expr, declared_type)
        else:
            self.push(expr, type)

        for i in self.try_frames:
            # XXX This should probably not copy the entire frame, but
            # just copy this variable into a single stored frame.
            self.allow_jump(i)

    def invalidate_dependencies(self, expr: Node) -> None:
        """Invalidate knowledge of types that include expr, but not expr itself.

        For example, when expr is foo.bar, invalidate foo.bar.baz.

        It is overly conservative: it invalidates globally, including
        in code paths unreachable from here.
        """
        for dep in self.dependencies.get(expr.literal_hash, set()):
            self._cleanse_key(dep)

    def most_recent_enclosing_type(self, expr: Node, type: Type) -> Type:
        if isinstance(type, AnyType):
            return self.get_declaration(expr)
        key = expr.literal_hash
        enclosers = ([self.get_declaration(expr)] +
                     [f[key] for f in self.frames
                      if key in f and is_subtype(type, f[key])])
        return enclosers[-1]

    def allow_jump(self, index: int) -> None:
        # self.frames and self.options_on_return have different lengths
        # so make sure the index is positive
        if index < 0:
            index += len(self.options_on_return)
        frame = Frame()
        for f in self.frames[index + 1:]:
            frame.update(f)
        self.options_on_return[index].append(frame)

    def push_loop_frame(self) -> None:
        self.loop_frames.append(len(self.frames) - 1)

    def pop_loop_frame(self) -> None:
        self.loop_frames.pop()

    @contextmanager
    def frame_context(self, fall_through: int = 0) -> Iterator[Frame]:
        """Return a context manager that pushes/pops frames on enter/exit.

        If fall_through > 0, then it will allow the frame to escape to
        its ancestor `fall_through` levels higher.

        A simple 'with binder.frame_context(): pass' will change the
        last_pop_* flags but nothing else.
        """
        was_breaking_out = self.breaking_out
        yield self.push_frame()
        self.pop_frame(fall_through)
        self.breaking_out = was_breaking_out
