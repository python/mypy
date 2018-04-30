#!/bin/bash -eux

# Build a debug build of python, install it, and create a venv for it
# This is mainly intended for use in our travis builds but there's no
# reason it couldn't be used locally.
# Usage: build-debug-python.sh <version> <install prefix> <venv location>

VERSION=$1
PREFIX=$2
VENV=$3
if [[ -f $PREFIX/bin/python3 ]]; then
    exit
fi

wget https://www.python.org/ftp/python/$VERSION/Python-$VERSION.tgz
tar zxf Python-$VERSION.tgz
cd Python-$VERSION
./configure CFLAGS='-DPy_DEBUG -DPy_TRACE_REFS -DPYMALLOC_DEBUG' --with-pydebug --prefix=$PREFIX
make -j4
make install
$PREFIX/bin/pip3 install virtualenv
$PREFIX/bin/python3 -m virtualenv $VENV
ln -s python3-config $PREFIX/bin/python-config
