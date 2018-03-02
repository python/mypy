"""AST triggers that are used for fine-grained dependency handling."""

WILDCARD_TAG = '[wildcard]'


def make_trigger(name: str) -> str:
    return '<%s>' % name


def make_wildcard_trigger(module: str) -> str:
    """Special trigger fired when any name is changes in a module.

    This is used for "from m import *" dependencies.
    """
    return '<%s%s>' % (module, WILDCARD_TAG)
