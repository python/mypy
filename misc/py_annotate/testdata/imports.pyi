# Following imports need to be copied into .py

from m1 import A
from m2 import B, C
import m3

from m4 import (D,
E)

from m5.m6 import F

from m7 import G # foo

if False:
    import m8

def g():
    import m9


from m10 import *

from m11 import m as n

from m12 import (a, b, c)

from m13 import (a, b, )

from m14 import a, b as c

from m15 import a as a1, b as b1


#asdasd
if False:
    import q1


# can't just look at first leaf's column to see if import is "top-level"
if False:
    \
import q2


# top-level, but first column is not 0
\
    import q3



from ......m16 import g

import existing_import

import o1 as o2


def f(x: a): ...




