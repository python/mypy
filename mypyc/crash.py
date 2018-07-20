from typing import NoReturn

import sys
import traceback


def crash_report(module_path: str, line: int) -> NoReturn:
    # Adapted from report_internal_error in mypy
    err = sys.exc_info()[1]
    tb = traceback.extract_stack()[:-2]
    # Excise all the traceback from the test runner
    for i, x in enumerate(tb):
        if x.name == 'pytest_runtest_call':
            tb = tb[i + 1:]
            break
    tb2 = traceback.extract_tb(sys.exc_info()[2])
    print('Traceback (most recent call last):')
    for s in traceback.format_list(tb + tb2):
        print(s.rstrip('\n'))
    print('{}:{}: {}: {}'.format(module_path, line, type(err).__name__, err))
    raise SystemExit(2)
