from typing import Iterable, Tuple, List, Optional


def module_prefix(modules: Iterable[str], target: str) -> Optional[str]:
    result = split_target(modules, target)
    if result is None:
        return None
    return result[0]


def split_target(modules: Iterable[str], target: str) -> Optional[Tuple[str, str]]:
    remaining = []  # type: List[str]
    while True:
        if target in modules:
            return target, '.'.join(remaining)
        components = target.rsplit('.', 1)
        if len(components) == 1:
            return None
        target = components[0]
        remaining.insert(0, components[1])
