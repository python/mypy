"""Shared logic between our three mypy parser files.
"""


def special_function_elide_names(name: str) -> bool:
    if name == "__init__" or name == "__new__":
        return False
    return name.startswith("__") and name.endswith("__")
