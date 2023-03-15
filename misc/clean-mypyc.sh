#!/bin/bash
echo "Cleaning C/C++ build artifacts..."
(cd mypyc/lib-rt || exit; make clean)
(cd mypyc/external/googletest/make || exit; make clean)
