#!/usr/bin/env bash
set -euo pipefail
test_sources=${1:?Pass the directory containing the three test checkouts}
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
for test_name in LowEFrag CCCStest Attenuation-ilantest; do
    cmake -S "$test_sources/$test_name" -B "$build_dir/$test_name" \
        -DPROJECT_NAME_OVERRIDE="$test_name" -DWITH_GEANT4_UIVIS=OFF
    cmake --build "$build_dir/$test_name" --parallel 2
done
