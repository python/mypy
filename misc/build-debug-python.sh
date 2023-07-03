#!/bin/bash -eux

# Build a debug build of python, install it, and create a venv for it
# This is mainly intended for use in our github actions builds but it can work
# locally. (Though it unfortunately uses brew on OS X to deal with openssl
# nonsense.)
# Usage: build-debug-python.sh <version> <install prefix> <venv location>
#
# Running it locally might look something like: mkdir -p ~/tmp/cpython-debug && cd ~/tmp/cpython-debug && ~/src/mypy/misc/build-debug-python.sh 3.6.6 ~/tmp/cpython-debug ~/src/mypy/env-debug

VERSION=$1
PREFIX=$2
VENV=$3
if [[ -f $PREFIX/bin/python3 ]]; then
    exit
fi

CPPFLAGS=""
LDFLAGS=""
if [[ $(uname) == Darwin ]]; then
    brew install openssl xz
    CPPFLAGS="-I$(brew --prefix openssl)/include"
    LDFLAGS="-L$(brew --prefix openssl)/lib"
fi

curl -O https://www.python.org/ftp/python/$VERSION/Python-$VERSION.tgz
tar zxf Python-$VERSION.tgz
cd Python-$VERSION
CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS" ./configure CFLAGS="-DPy_DEBUG -DPy_TRACE_REFS -DPYMALLOC_DEBUG" --with-pydebug --prefix=$PREFIX --with-trace-refs
make -j4
make install
$PREFIX/bin/python3 -m pip install virtualenv
$PREFIX/bin/python3 -m virtualenv $VENV
ln -s python3-config $PREFIX/bin/python-config
