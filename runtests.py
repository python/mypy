#!/usr/bin/env python3
from os import system
from sys import argv, exit

prog, *args = argv

cmds = {
    'self': 'python3 -m mypy --config-file mypy_self_check.ini -p mypy',
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
