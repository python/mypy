#!/bin/bash -ex

# Usage: misc/test_installed_version.sh [wheel] [python command]
# Installs a version of mypy into a virtualenv and tests it.

# A bunch of stuff about mypy's code organization and test setup makes
# it annoying to test an installed version of mypy. If somebody has a
# better way please let me know.

function abspath {
    python3 -c "import os.path; print(os.path.abspath('$1'))"
}

TO_INSTALL="${1-.}"
PYTHON="${2-python3}"
VENV="$(mktemp -d -t mypy-test-venv.XXXXXXXXXX)"
trap "rm -rf '$VENV'" EXIT

"$PYTHON" -m virtualenv "$VENV"
source "$VENV/bin/activate"

ROOT="$PWD"
TO_INSTALL="$(abspath "$TO_INSTALL")"

# Change directory so we can't pick up any of the stuff in the root.
# We need to do this before installing things too because I was having
# the current mypy directory getting picked up as satisfying the
# requirement (argh!)
cd "$VENV"

pip install -r "$ROOT/test-requirements.txt"
pip install $TO_INSTALL

# pytest looks for configuration files in the parent directories of
# where the tests live. Since we are trying to run the tests from
# their installed location, we copy those into the venv. Ew ew ew.
cp "$ROOT/pytest.ini" "$ROOT/conftest.py" "$VENV/"

# Find the directory that mypy tests were installed into
MYPY_TEST_DIR="$(python3 -c 'import mypy.test; print(mypy.test.__path__[0])')"
# Run the mypy tests
MYPY_TEST_PREFIX="$ROOT" python3 -m pytest "$MYPY_TEST_DIR"/test*.py
