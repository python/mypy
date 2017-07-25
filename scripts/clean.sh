#!/bin/bash
echo "Cleaning C/C++ build artifacts..."
(cd lib-rt; make clean)
(cd googletest/make; make clean)
