"""AST triggers that are used for fine-grained dependency handling."""


def make_trigger(name: str) -> str:
    return '<%s>' % name
