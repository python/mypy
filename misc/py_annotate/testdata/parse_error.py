# syntax error doesn't get detected by 2to3

def f(*): pass


# Gets parsed as:
# Node(funcdef,
#      [Leaf(1, 'def'), Leaf(1, 'f'),
#       Node(parameters, [Leaf(7, '('), Leaf(16, '*'), Leaf(8, ')')]),
#       Leaf(11, ':'),
#       Node(simple_stmt, [Leaf(1, 'pass')])])
