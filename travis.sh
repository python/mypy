#!/bin/bash

# Travis CI script that does these things:
#  - run tests
#  - type check the implementation
#  - type check stubs
#  - type check example code (for regression testing)
#  - run a linter to catch style issues (flake8)

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
for subdir in typeshed/builtins/3* typeshed/stdlib/3*; do
  pushd $subdir > /dev/null
  import=$(ls *.pyi | sed s/\\.pyi//g | sed "s/^/import /g")
  popd > /dev/null
  echo "$import" >> $STUBTEST
done
for m in os os.path; do
    echo "import $m" >> $STUBTEST
done

NUMSTUBS=$(( `wc -l $STUBTEST | cut -d' ' -f1` - 1 ))

echo Type checking $NUMSTUBS stubs...
echo
"$PYTHON" "$DRIVER" $STUBTEST || fail
rm $STUBTEST

# Checks sample code

echo Type checking lib-python...
echo
pushd lib-python/3.2 > /dev/null
for f in test/test_*.py; do
    mod=test.`basename "$f" .py`
    echo $mod
    "$PYTHON" "$DRIVER" -m $mod || fail
done
popd > /dev/null

echo Linting...
echo
./lint.sh || fail

exit $result
