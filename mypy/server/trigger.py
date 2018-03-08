"""AST triggers that are used for fine-grained dependency handling."""

# Used as a suffix for triggers to handle "from m import *" dependencies (see also
# make_wildcard_trigger)
WILDCARD_TAG = '[wildcard]'


def make_trigger(name: str) -> str:
    return '<%s>' % name


def make_wildcard_trigger(module: str) -> str:
    """Special trigger fired when any top-level name is changed in a module.

    This is used for "from m import *" dependencies.
    """
    return '<%s%s>' % (module, WILDCARD_TAG)
