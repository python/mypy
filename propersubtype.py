from mtypes import Instance
from subtypes import is_subtype


def is_proper_subtype(t, s):
    """Check if t is a proper subtype of s (no need to rely on compatibility due
    to dynamic types).
    """
    # FIX support generic types, tuple types etc.
    return isinstance(t, Instance) and isinstance(s, Instance) and t.args == [] and s.args == [] and is_subtype(t, s)
