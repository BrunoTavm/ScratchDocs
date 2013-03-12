#!/bin/bash
# help migrate tasks between iterations. arguments are previous iteration & new iteration.
FROM=$1
TO=$2

find $FROM'/' -type d -maxdepth 1 ! -wholename $FROM'/' -exec git mv {} $TO'/' \; -print
find $TO'/' -type d -maxdepth 1 ! -wholename $TO'/'  -exec ln -s '../{}' $FROM'/' \; -print
git add $FROM'/*'
