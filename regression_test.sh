#!/bin/bash

set -e

for file in $(git ls-files | grep '\.texp$'); do
    dir=${file%/*}
    target=${file##*/}
    pushd $dir >/dev/null
    rm -f $target
    echo -n "$dir> "
    make $target
    git diff $target |cat && echo OK
    popd >/dev/null
done
