#!/usr/bin/env python3
from sys import exit
from os import system
import sys

prog, *args = sys.argv

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
