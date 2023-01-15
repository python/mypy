#!/bin/bash
# Internal wrapper script used to run commands in a container

# Copy all the files we need from the mypy repo directory shared with
# the host to a local directory. Accessing files using a shared
# directory on a mac can be *very* slow.
echo "copying files to the container..."
cp -R /repo/{mypy,mypyc,test-data,misc} .
cp /repo/{pytest.ini,conftest.py,runtests.py,pyproject.toml,setup.cfg} .
cp /repo/{mypy_self_check.ini,mypy_bootstrap.ini} .

# Run the wrapped command
"$@"
