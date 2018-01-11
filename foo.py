from typing import Any

import attr


def validator(inst: Any, attr: attr.Attribute, value: bool):
    pass


def converter(val: Any) -> bool:
    return bool(val)


a = attr.ib()  # E: Need type annotation for variable
b = attr.ib(7)
c = attr.ib(validator=validator)  # E: Need type annotation for variable
d = attr.ib(True, validator=validator)
e = attr.ib(type=str)

attr.ib(validator=None)

f = attr.ib(validator=validator, convert=converter)  # E: Need type annotation for variable



reveal_type(a)  # E: Revealed type is 'Any' # E: Cannot determine type of 'a'
reveal_type(b)  # E: Revealed type is 'Any'
reveal_type(c)  # E: Revealed type is 'Any'  # E: Cannot determine type of 'c'
reveal_type(d)  # E: Revealed type is 'builtins.int*'
reveal_type(e)
