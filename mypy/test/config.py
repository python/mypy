import os
import os.path

import typing


this_file_dir = os.path.dirname(os.path.realpath(__file__))
PREFIX = os.path.dirname(os.path.dirname(this_file_dir))

# Location of test data files such as test case descriptions.
test_data_prefix = os.path.join(PREFIX, 'test-data', 'legacy-unit')

assert os.path.isdir(test_data_prefix), \
    'Test data prefix ({}) not set correctly'.format(test_data_prefix)

# Temp directory used for the temp files created when running test cases.
# This is *within* the tempfile.TemporaryDirectory that is chroot'ed per testcase.
# It is also hard-coded in numerous places, so don't change it.
test_temp_dir = 'tmp'
