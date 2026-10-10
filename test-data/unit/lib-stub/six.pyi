from typing import Type, Callable
def with_metaclass(mcls: Type[type], *args: type) -> type: pass
def add_metaclass(mcls: Type[type]) -> Callable[[type], type]: pass
