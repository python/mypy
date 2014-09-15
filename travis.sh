#!/bin/bash

PYTHON=python

result=0

fail()
{
    result=1
}

# Setup stuff

DRIVER=$PWD/scripts/mypy
export PYTHONPATH=`pwd`/lib-typing/3.2:`pwd`

# Basic tests

echo Running tests...
echo
echo tests.py
"$PYTHON" "$DRIVER" tests.py || fail
"$PYTHON" tests.py || fail
for t in mypy.test.testpythoneval; do
    echo $t
    "$PYTHON" "$DRIVER" -m $t || fail
done

# Stub checks

STUBTEST=_test_stubs.py
echo "import typing" > $STUBTEST
cd stubs/3.2
ls *.py | sed s/\\.py//g | sed "s/^/import /g" >> ../../$STUBTEST
for m in os os.path; do
    echo "import $m" >> ../../$STUBTEST
done
cd ../..

NUMSTUBS=$(( `wc -l $STUBTEST | cut -d' ' -f1` - 1 ))

echo Type checking $NUMSTUBS stubs...
echo
"$PYTHON" "$DRIVER" $STUBTEST || fail
rm $STUBTEST

# Sample checks

# Only run under 3.2

if [ "`"$PYTHON" -c 'from sys import version_info as vi; print(vi.major, vi.minor)'`" == "3 2" ]; then
    echo Type checking lib-python...
    echo
    cd lib-python/3.2
    for f in test/test_*.py; do
        mod=test.`basename "$f" .py`
        echo $mod
        "$PYTHON" "$DRIVER" -m $mod || fail
    done
else
    echo "Skipping lib-python type checks (not Python 3.2!)"
fi

exit $result
