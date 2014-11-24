#!/bin/sh

# Remove trailing whitespace from all non-binary files in a git repo.

# From https://gist.github.com/dpaluy/3690668; originally from here:
# http://unix.stackexchange.com/questions/36233/how-to-skip-file-in-sed-if-it-contains-regex/36240#36240

git grep -I --name-only -z -e '' | xargs -0 sed -i -e 's/[ \t]\+\(\r\?\)$/\1/'
