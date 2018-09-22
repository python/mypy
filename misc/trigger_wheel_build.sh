#!/bin/bash -eu

REPO=travis-testing

set -x
git clone --recurse-submodules https://${GH_TOKEN}@github.com/$REPO.git

git config --global user.email "nobody"
git config --global user.name "mypy wheels autopush"

COMMIT=$(git rev-parse HEAD)
cd $REPO/mypy
git fetch
git checkout $COMMIT
V=$(python3 -m mypy --version| cut -d" " -f2)
cd ..
git commit -am "Build wheels for mypy $V"
git tag v$V
git push --tags origin master
