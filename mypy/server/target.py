from typing import Iterable, Tuple


def module_prefix(modules: Iterable[str], target: str) -> str:
    return split_target(modules, target)[0]


def split_target(modules: Iterable[str], target: str) -> Tuple[str, str]:
    remaining = []
    while True:
        if target in modules:
            return target, '.'.join(remaining)
        components = target.rsplit('.', 1)
        if len(components) == 1:
            assert False, 'Cannot find module prefix for {}'.format(target)
        target = components[0]
        remaining.insert(0, components[1])
