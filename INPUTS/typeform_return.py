def return_type() -> type:
    # E: Incompatible return value type (got "UnionType", expected "type")  [return-value]
    return str | None

return_type()
