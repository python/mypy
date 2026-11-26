def identity(value):
    return value


a: int = identity(42)
b: str = identity("hello")
c: list[int] = identity([1, 2, 3])
