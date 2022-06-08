
"""Stand-alone test file for issue #12352"""

# Passes with legacy mypy.
def f1_str_annotated(ekr_a: str="abc") -> None:
    pass

# Fails with legacy mypy.
def f2_str_not_annotated(ekr_b="abc") -> None:
    pass
