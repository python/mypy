"""The "mypy.typing" module defines experimental extensions to the standard
"typing" module that is supported by the mypy typechecker.
"""


def TypedDict(typename, fields):
    """TypedDict creates a dictionary type that expects all of its
    instances to have a certain common set of keys, with each key
    associated with a value of a consistent type. This expectation
    is not checked at runtime but is only enforced by typecheckers.
    """
    def new_dict(*args, **kwargs):
        return dict(*args, **kwargs)

    new_dict.__name__ = typename
    new_dict.__supertype__ = dict
    return new_dict
