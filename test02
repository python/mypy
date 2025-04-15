#!/bin/bash
# while-read: read lines from a file
count=0

while read -r LINE; do
	printf "%s| %s\n" "$count" "$LINE"
	count=$(expr $count + 1)
done <$1
