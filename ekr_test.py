
"""Stand-alone test file for issue #12352"""

# Passes with legacy mypy.
# def ekr_f_annotated_initialized(a: str="abc") -> None:
    # pass

# def ekr_f_annotated(a: str) -> None:
    # pass

# Fails with legacy mypy.
# Change this case!
def ekr_f_not_annotated(a="abc") -> None:
    pass
    
# Later
# def ekr_f_not_annotated2(b, a="abc") -> None:
    # pass
    
# a: str="abc"
# b="xyz"
# c: str
