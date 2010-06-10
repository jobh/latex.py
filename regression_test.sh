#!/bin/bash
set -e

for file in $(git ls-files | grep '\.texp$'); do
    dir=${file%/*}
    target=${file##*/}
    pushd $dir >/dev/null
    for PYTHON in python3 python2.6; do
        rm -f $target
        echo -n "$PYTHON $dir\$ "
        make PYTHON=$python $target
        PAGER= git diff --exit-code $target || { echo "! $file failed with $PYTHON"; exit 1; }
    done
    popd >/dev/null
done
