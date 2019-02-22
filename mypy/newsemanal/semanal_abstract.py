"""Calculate the abstract status of classes.

This happens after semantic analysis and before type checking.
"""

from typing import List, Set, Optional

from mypy.nodes import Node, MypyFile, SymbolTable, TypeInfo, Var, Decorator, OverloadedFuncDef
from mypy.errors import Errors


def calculate_abstract_status(file: MypyFile, errors: Errors) -> None:
    """Calculate the abstract status of all classes in the symbol table in file.

    Also check that ABCMeta is used correctly.
    """
    process(file.names, file.is_stub, file.fullname(), errors)


def process(names: SymbolTable, is_stub_file: bool, prefix: str, errors: Errors) -> None:
    for name, symnode in names.items():
        node = symnode.node
        if isinstance(node, TypeInfo) and node.fullname().startswith(prefix):
            calculate_class_abstract_status(node, is_stub_file, errors)
            new_prefix = prefix + '.' + node.name()
            process(node.names, is_stub_file, new_prefix, errors)


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
