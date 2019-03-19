"""This file exists as a temporary measure, and will be removed when new
semantic analyzer is the default one.
"""
MYPY = False
if MYPY:
    from typing_extensions import Final

# Files to not run with new semantic analyzer.
new_semanal_blacklist = [
    'check-async-await.test',
    'check-expressions.test',
    'check-flags.test',
    'check-functions.test',
    'check-incremental.test',
    'check-literal.test',
    'check-overloading.test',
    'check-python2.test',
    'check-statements.test',
    'check-unions.test',
    'check-unreachable-code.test',
]  # type: Final
