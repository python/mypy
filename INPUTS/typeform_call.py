def expect_type(typ: type) -> None:
    pass

# E: Argument 1 to "expect_type" has incompatible type "UnionType"; expected "type"  [arg-type]
expect_type(str | None)
