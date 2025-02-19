typ: type
typ = int

# E: Incompatible types in assignment (expression has type "UnionType", variable has type "type")  [assignment]
typ = str | None

# from typing_extensions import TypeExpr as TypeForm
# typx: TypeForm
# typx = int | None
