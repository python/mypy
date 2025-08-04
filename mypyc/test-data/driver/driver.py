"""Default driver for run tests (run-*.test).

This imports the 'native' module (containing the compiled test cases)
and calls each function starting with test_, and reports any
exceptions as failures.

Test cases can provide a custom driver.py that overrides this file.
"""

import sys
import native
import asyncio
import inspect

evloop = asyncio.new_event_loop()

failures = []
tests_run = 0

for name in dir(native):
    if name.startswith('test_'):
        test_func = getattr(native, name)
        tests_run += 1
        try:
            if inspect.iscoroutinefunction(test_func):
                evloop.run_until_complete(test_func)
            else:
                test_func()
        except Exception as e:
            failures.append((name, sys.exc_info()))

if failures:
    from traceback import print_exception, format_tb
    import re

    def extract_line(tb):
        formatted = '\n'.join(format_tb(tb))
        m = re.search('File "(native|driver).py", line ([0-9]+), in (test_|<module>)', formatted)
        if m is None:
            return "0"
        return m.group(1)

    # Sort failures by line number of test function.
    failures = sorted(failures, key=lambda e: extract_line(e[1][2]))

    # If there are multiple failures, print stack traces of all but the final failure.
    for name, e in failures[:-1]:
        print(f'<< {name} >>')
        sys.stdout.flush()
        print_exception(*e)
        print()
        sys.stdout.flush()

    # Raise exception for the last failure. Test runner will show the traceback.
    print(f'<< {failures[-1][0]} >>')
    sys.stdout.flush()
    raise failures[-1][1][1]

assert tests_run > 0, 'Default test driver did not find any functions prefixed "test_" to run.'
