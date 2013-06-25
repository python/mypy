import os
import os.path
import typing

PREFIX = ''

# Location of test data files such as test case descriptions.
test_data_prefix = os.path.join(PREFIX, 'test', 'data')

assert os.path.isdir(test_data_prefix), \
        'Test data prefix ({}) not set correctly'.format(test_data_prefix)

# Temp directory used for the temp files created when running test cases.
test_temp_dir = os.path.join(PREFIX, 'tmp')

if not os.path.isdir(test_temp_dir):
    os.mkdir(test_temp_dir)

assert os.path.isdir(test_temp_dir), \
        'Test temp dir ({}) not set correctly'.format(test_temp_dir)
