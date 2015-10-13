import os
import os.path

import typing


# Location of test data files such as test case descriptions.
test_data_prefix = os.path.join(os.path.dirname(__file__), 'data')

assert os.path.isdir(test_data_prefix), \
    'Test data prefix ({}) not set correctly'.format(test_data_prefix)

# Temp directory used for the temp files created when running test cases.
# This is *within* the tempfile.TemporaryDirectory that is chroot'ed per testcase.
# It is also hard-coded in numerous places, so don't change it.
test_temp_dir = 'tmp'
