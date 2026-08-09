#!/bin/bash
echo "Cleaning C/C++ build artifacts..."
(cd mypyc/lib-rt; make clean)
(cd mypyc/external/googletest/make; make clean)
