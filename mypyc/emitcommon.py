from typing import List

from mypyc.common import REG_PREFIX
from mypyc.ops import Environment, Label, Register, RTType, TupleRTType


class Emitter:
    """Helper for C code generation."""

    def __init__(self, env: Environment = None) -> None:
        self.env = env or Environment()
        self.fragments = []  # type: List[str]
        self._indent = 0

    def indent(self) -> None:
        self._indent += 4

    def dedent(self) -> None:
        self._indent -= 4
        assert self._indent >= 0

    def label(self, label: Label) -> str:
        return 'CPyL%d' % label

    def reg(self, reg: Register) -> str:
        name = self.env.names[reg]
        return REG_PREFIX + name

    def emit_line(self, line: str = '') -> None:
        if line.startswith('}'):
            self.dedent()
        self.fragments.append(self._indent * ' ' + line + '\n')
        if line.endswith('{'):
            self.indent()

    def emit_lines(self, *lines: str) -> None:
        for line in lines:
            self.emit_line(line)

    def emit_label(self, label: Label) -> None:
        # Extra semicolon prevents an error when the next line declares a tempvar
        self.fragments.append('{}: ;\n'.format(self.label(label)))

    def emit_from_emitter(self, emitter: 'Emitter') -> None:
        self.fragments.extend(emitter.fragments)


def emit_inc_ref(dest: str, rtype: RTType, emitter: Emitter) -> None:
    """Increment reference count of C expression `dest`.

    For composite unboxed structures (e.g. tuples) recursively
    increment reference counts for each component.
    """
    if rtype.name == 'int':
        emitter.emit_line('CPyTagged_IncRef(%s);' % dest)
    elif isinstance(rtype, TupleRTType):
        for i, item_type in enumerate(rtype.types):
            emit_inc_ref('{}.f{}'.format(dest, i), item_type, emitter)
    elif not rtype.supports_unbox:
        emitter.emit_line('Py_INCREF(%s);' % dest)
    # Otherwise assume it's an unboxed, pointerless value and do nothing.


def emit_dec_ref(dest: str, rtype: RTType, emitter: Emitter) -> None:
    """Decrement reference count of C expression `dest`.

    For composite unboxed structures (e.g. tuples) recursively
    decrement reference counts for each component.
    """
    if rtype.name == 'int':
        emitter.emit_line('CPyTagged_DecRef(%s);' % dest)
    elif isinstance(rtype, TupleRTType):
        for i, item_type in enumerate(rtype.types):
            emit_dec_ref('{}.f{}'.format(dest, i), item_type, emitter)
    elif not rtype.supports_unbox:
        emitter.emit_line('Py_DECREF(%s);' % dest)
    # Otherwise assume it's an unboxed, pointerless value and do nothing.
