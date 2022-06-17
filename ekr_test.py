"""Stand-alone test file for issue #12352"""

# def ekr_f_annotated(ekr_a: str) -> None:
    # pass
    
# Passes with legacy mypy.
# def ekr_f_annotated_initialized(ekr_a: str="abc") -> None:
    # pass

# Fails with legacy mypy.
# Change this case!
def ekr_f_not_annotated(ekr_a="abc") -> None:
    pass
    
# Later
# def ekr_f_not_annotated2(b, ekr_a="abc") -> None:
    # pass
    
# a: str="abc"
# b="xyz"
# c: str
