#!/bin/bash -ex
MYPYC_DIR=~/src/mypyc
REV=$(cd "$MYPYC_DIR" && git rev-parse HEAD)
VERSION=$(cd "$MYPYC_DIR" && python3 -c 'from mypyc.version import __version__; print(__version__)')

echo "git+https://github.com/mypyc/mypyc.git@$REV#egg=mypyc==$VERSION" > mypyc-requirements.txt
git commit -a -m "Update pinned mypyc version to $VERSION"
