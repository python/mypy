"""Calculate some properties of classes.

These happen after semantic analysis and before type checking.
"""

from typing import List, Set, Optional

from mypy.nodes import Node, TypeInfo, Var, Decorator, OverloadedFuncDef
from mypy.types import Instance
from mypy.errors import Errors


def calculate_class_abstract_status(typ: TypeInfo, is_stub_file: bool, errors: Errors) -> None:
    """Calculate abstract status of a class.

    Set is_abstract of the type to True if the type has an unimplemented
    abstract attribute.  Also compute a list of abstract attributes.
    Report error is required ABCMeta metaclass is missing.
    """
    concrete = set()  # type: Set[str]
    abstract = []  # type: List[str]
    abstract_in_this_class = []  # type: List[str]
    for base in typ.mro:
        for name, symnode in base.names.items():
            node = symnode.node
            if isinstance(node, OverloadedFuncDef):
                # Unwrap an overloaded function definition. We can just
                # check arbitrarily the first overload item. If the
                # different items have a different abstract status, there
                # should be an error reported elsewhere.
                func = node.items[0]  # type: Optional[Node]
            else:
                func = node
            if isinstance(func, Decorator):
                fdef = func.func
                if fdef.is_abstract and name not in concrete:
                    typ.is_abstract = True
                    abstract.append(name)
                    if base is typ:
                        abstract_in_this_class.append(name)
            elif isinstance(node, Var):
                if node.is_abstract_var and name not in concrete:
                    typ.is_abstract = True
                    abstract.append(name)
                    if base is typ:
                        abstract_in_this_class.append(name)
            concrete.add(name)
    # In stubs, abstract classes need to be explicitly marked because it is too
    # easy to accidentally leave a concrete class abstract by forgetting to
    # implement some methods.
    typ.abstract_attributes = sorted(abstract)
    if is_stub_file:
        if typ.declared_metaclass and typ.declared_metaclass.type.fullname() == 'abc.ABCMeta':
            return
        if typ.is_protocol:
            return
        if abstract and not abstract_in_this_class:
            def report(message: str, severity: str) -> None:
                errors.report(typ.line, typ.column, message, severity=severity)

            attrs = ", ".join('"{}"'.format(attr) for attr in sorted(abstract))
            report("Class {} has abstract attributes {}".format(typ.fullname(), attrs), 'error')
            report("If it is meant to be abstract, add 'abc.ABCMeta' as an explicit metaclass",
                   'note')


def check_protocol_status(info: TypeInfo, errors: Errors) -> None:
    """Check that all classes in MRO of a protocol are protocols"""
    if info.is_protocol:
        for type in info.bases:
            if not isinstance(type, Instance) or not type.type.is_protocol:
                if type.type.fullname() != 'builtins.object':
                    def report(message: str, severity: str) -> None:
                        errors.report(info.line, info.column, message, severity=severity)
                    report('All bases of a protocol must be protocols', 'error')


def calculate_class_vars(info: TypeInfo) -> None:
    """Try to infer additional class variables.

    Subclass attribute assignments with no type annotation are assumed
    to be classvar if overriding a declared classvar from the base
    class.

    This must happen after the main semantic analysis pass, since
    this depends on base class bodies having been fully analyzed.
    """
    for name, sym in info.names.items():
        node = sym.node
        if isinstance(node, Var) and node.info and node.is_inferred and not node.is_classvar:
            for base in info.mro[1:]:
                member = base.names.get(name)
                if (member is not None
                        and isinstance(member.node, Var)
                        and member.node.is_classvar):
                    node.is_classvar = True
