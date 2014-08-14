#!/bin/bash

# Setup stuff

DRIVER=$PWD/scripts/mypy
export PYTHONPATH=`pwd`/lib-typing/3.2:`pwd`

# Basic tests

echo Running tests...
echo
echo tests.py
python "$DRIVER" tests.py
for t in mypy.test.testpythoneval mypy.test.testcgen; do
    echo $t
    python "$DRIVER" -m $t
done

# Stub checks

STUBTEST=_test_stubs.py
cd stubs/3.2
ls *.py | sed s/\\.py//g | sed "s/^/import /g" > $STUBTEST
for m in os os.path; do
    echo "import $m" >> $STUBTEST
done

echo Type checking stubs...
echo
python "$DRIVER" -S $STUBTEST
rm $STUBTEST
cd ..

# Sample checks



# Only run under 3.2

if [ "`python -c 'from sys import version_info as vi; print(vi.major, vi.minor)'`" == "3 3" ]; then
    echo Type checking lib-python...
    echo
    cd lib-python/3.2
    for f in test/test_*.py; do
        mod=test.`basename "$f" .py`
        echo $mod
        python "$DRIVER" -S -m $mod
    done
else
    echo "Skipping lib-python type checks(Not Python 3.2!)"
fi
