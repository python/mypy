#!/bin/bash

PYTHON=${PYTHON-python}

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
    "$PYTHON" -m $t || fail
done

# Stub checks

STUBTEST=_test_stubs.py
echo "import typing" > $STUBTEST
cd stubs/3.2
ls *.pyi | sed s/\\.pyi//g | sed "s/^/import /g" >> ../../$STUBTEST
for m in os os.path; do
    echo "import $m" >> ../../$STUBTEST
done
cd ../..

NUMSTUBS=$(( `wc -l $STUBTEST | cut -d' ' -f1` - 1 ))

echo Type checking $NUMSTUBS stubs...
echo
"$PYTHON" "$DRIVER" $STUBTEST || fail
rm $STUBTEST

# Checks sample code

echo Type checking lib-python...
echo
cd lib-python/3.2
for f in test/test_*.py; do
    mod=test.`basename "$f" .py`
    echo $mod
    "$PYTHON" "$DRIVER" -m $mod || fail
done

exit $result
