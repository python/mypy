import os
PYTHON2_VERSION = (2, 7)
PYTHON3_VERSION = (3, 6)
CACHE_DIR = '.mypy_cache'
CONFIG_FILE = 'mypy.ini'


def allow_fixtures() -> bool:
    return not os.environ.get('NO_BUILTINS_FIXTURES', False)
