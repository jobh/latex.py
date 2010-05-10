#!/bin/bash

for file in $(git ls-files | grep '\.texp$'); do
    dir=${file%/*}
    target=${file##*/}
    pushd $dir >/dev/null
    rm -f $target
    echo -n "$dir> "
    make $target
    PAGER= git diff --exit-code $target || { echo "! $file failed"; exit 1; }
    popd >/dev/null
done
