#!/bin/bash -eux

# Trigger a build of mypyc compiled mypy wheels by updating the mypy
# submodule in the git repo that drives those builds.

# TODO: This is a testing repo and will need to be retargeted at the
# real location once it exists. $WHEELS_PUSH_TOKEN is stored in travis
# and is an API token for the mypy-build-bot account.
git clone --recurse-submodules https://${WHEELS_PUSH_TOKEN}@github.com/msullivan/travis-testing.git build

git config --global user.email "nobody"
git config --global user.name "mypy wheels autopush"

COMMIT=$(git rev-parse HEAD)
cd build/mypy
git fetch
git checkout $COMMIT
pip install -r test-requirements.txt
V=$(python3 -m mypy --version)
V=$(echo "$V" | cut -d" " -f2)
cd ..
git commit -am "Build wheels for mypy $V"
git tag v$V
git push --tags origin master
