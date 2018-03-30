from __future__ import print_function
# NOTE: This file must remain compatible with Python 2


from distutils.sysconfig import get_python_lib
import site
from typing import List


def getsitepackages():
    # type: () -> List[str]
    if hasattr(site, 'getusersitepackages') and hasattr(site, 'getsitepackages'):
        user_dir = site.getusersitepackages()
        return site.getsitepackages() + [user_dir]
    else:
        return [get_python_lib()]


if __name__ == '__main__':
    print(repr(getsitepackages()))
