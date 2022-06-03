#@+leo-ver=5-thin
#@+node:ekr.20220603080610.1: * @file ekr_test.py
"""Stand-alone test file for issue #12352"""

# mypy's type checking should create the equivant of:
    
# def f_str(a: str="abc") -> None

def f1_str(a="abc") -> None:
    pass
#@-leo
