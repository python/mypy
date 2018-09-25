#!/usr/bin/env python3
from os import system
from sys import argv, exit, platform

prog, *args = argv

if platform == 'win32':
    python_name = 'py -3'
else:
    python_name = 'python3'

cmds = {
    'self': python_name + ' -m mypy --config-file mypy_self_check.ini -p mypy',
    'lint': 'flake8 -j0',
    'pytest': 'pytest'
}

if not set(args).issubset(cmds):
    print("usage:", prog, " ".join('[%s]' % k for k in cmds))
    exit(1)

if not args:
    args = list(cmds)

for arg in args:
    cmd = cmds[arg]
    print('$', cmd)
    res = (system(cmd) & 0x7F00) >> 8
    if res:
        exit(res)
