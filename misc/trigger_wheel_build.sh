#!/bin/bash -eux

git clone --recurse-submodules https://${GH_TOKEN}@github.com/msullivan/travis-testing.git build

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
