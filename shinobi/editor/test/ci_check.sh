#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# CI check for the keymap editor, also runnable by hand on Linux or in WSL (from a clone with tags).
# usage: ci_check.sh <qmk_firmware dir> <work dir>
#   <qmk_firmware dir> is set up at the pinned commit (build_firmware.sh clones it if missing).
# The editor patches release images, so each release in shinobi_data.js is tested against its own sources:
#   1. a tagged release: download its image and check the SHA-256, and unpack the shinobi folder at the tag with this
#      checkout's editor laid over it. A release not tagged yet (being prepared): the sources are this checkout, and
#      a build of its default keymap with the release's build date must reproduce the SHA-256 in shinobi_data.js;
#   2. regenerate shinobi_data.js from all of them: it must equal the committed one;
#   3. run byte_identity.sh for each release in its own sources (the default export compiles to the release; a
#      patched image equals its build).
# Exits non-zero if any step fails. Prints one TIMING line per step.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
shinobi="$(cd "$here/../.." && pwd)"
repo="$(cd "$shinobi/.." && pwd)"
qmk_dir="$1"; work="$2"
timing() { echo "TIMING label=$1 start=$2 end=$(date +%s) seconds=$(( $(date +%s) - $2 )) result=$3"; }
# Host keyboard layouts need no release: macro text per layout, labels and keymap.json (prints its own TIMING line).
node "$here/host_layouts.cjs"
rm -rf "$work"; mkdir -p "$work/release"
# One line per release: tag file sha256 build_date
mapfile -t releases < <(node -e 'require(process.argv[1]); for (const r of globalThis.SHINOBI_DATA.releases) console.log([r.tag, r.file, r.sha256, r.build_date].join(" "))' "$shinobi/editor/shinobi_data.js")
gen_args=()
for line in "${releases[@]}"; do
    read -r tag file sha date_str <<< "$line"
    src="$work/src_$tag"; mkdir -p "$src"
    t=$(date +%s)
    if git -C "$repo" rev-parse -q --verify "refs/tags/$tag^{commit}" > /dev/null; then
        curl -fsSL --retry 3 -m 120 -o "$work/release/$file" "https://github.com/cyclistmass/tex-qmk/releases/download/$tag/$file"
        echo "$sha  $work/release/$file" | sha256sum -c -
        git -C "$repo" archive "$tag" shinobi | tar -x -C "$src"
        rm -rf "$src/shinobi/editor"
        cp -r "$shinobi/editor" "$src/shinobi/editor"
        timing "release_$tag" "$t" ok
    else
        cp -r "$shinobi" "$src/shinobi"
        bash "$src/shinobi/editor/test/build_wsl.sh" "$qmk_dir" "$src/shinobi/qmk/keymaps/default/keymap.c" "$date_str" "$work/release/$file"
        if echo "$sha  $work/release/$file" | sha256sum -c -; then
            echo "PASS $tag is not tagged yet: this checkout, built with $date_str, reproduces its sha256"
            timing "prerelease_$tag" "$t" ok
        else
            echo "FAIL $tag is not tagged yet, and this checkout's build differs from shinobi_data.js: rebuild the image and regenerate it (see shinobi/editor/README.md)"
            timing "prerelease_$tag" "$t" fail; exit 1
        fi
    fi
    gen_args+=("$tag" "$work/release/$file" "$date_str")
done

t=$(date +%s)
python3 -I "$shinobi/tools/gen_editor_data.py" --out "$work/shinobi_data.js" "$qmk_dir" "${gen_args[@]}"
if cmp -s "$work/shinobi_data.js" "$shinobi/editor/shinobi_data.js"; then
    echo "PASS shinobi_data.js matches the releases' sources"; timing data_check "$t" ok
else
    echo "FAIL shinobi_data.js is stale: regenerate it with gen_editor_data.py (see shinobi/editor/README.md)"
    diff <(tr ',' '\n' < "$work/shinobi_data.js") <(tr ',' '\n' < "$shinobi/editor/shinobi_data.js") | head -20 || true
    timing data_check "$t" fail; exit 1
fi

for line in "${releases[@]}"; do
    read -r tag file _ _ <<< "$line"
    t=$(date +%s)
    bash "$work/src_$tag/shinobi/editor/test/byte_identity.sh" "$work/release/$file" "$work/out_$tag" "$qmk_dir"
    timing "byte_identity_$tag" "$t" ok
done
