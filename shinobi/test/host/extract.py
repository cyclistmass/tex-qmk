# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Copy named pieces of the firmware sources into one C file, so host tests run the real code against stubs.

usage: python3 -I extract.py <qmk dir> <out.c>

PIECES lists, per source file, the functions (copied whole, by brace matching) and the declaration lines
(matched by a regular expression) the tests need. A piece that isn't found exactly once is an error, so a rename
in the firmware fails the test instead of testing stale code.
"""
import re
import sys

PIECES = {
    "shinobi.c": [
        ("line", r"^static uint8_t\s+fn_scroll;"),
        ("line", r"^static uint16_t fn_scroll_time;"),
        ("line", r"^static bool\s+mid_key;"),
        ("func", "fn_scroll_record"),
        ("line", r"^#define MK_(UP|DOWN|LEFT|RIGHT)\b"),
        ("line", r"^static uint8_t\s+mk_held, mk_ticks;"),
        ("func", "mousekey_record"),
    ],
    "power.c": [
        ("line", r"^#define TYPE_SETTLE_MS\b"),
        ("func", "type_event"),
        ("func", "type_begin"),
        ("func", "type_end"),
        ("func", "macro_play"),
        ("line", r"^static const char\s+type_punct\[\]"),
        ("line", r"^static const uint8_t type_punct_code\[\]"),
        ("func", "type_text"),
    ],
}


def function(src, name):
    heads = [m for m in re.finditer(r"^[A-Za-z][\w \*]*\b" + name + r"\([^;{]*\)\s*\{", src, re.M)]
    if len(heads) != 1:
        sys.exit(f"extract.py: function {name} found {len(heads)} times")
    i, depth = heads[0].end() - 1, 0
    for j in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            return src[heads[0].start() : j + 1]
    sys.exit(f"extract.py: function {name} has no closing brace")


def lines(src, pattern):
    found = [l for l in src.splitlines() if re.search(pattern, l)]
    want = 4 if pattern.startswith("^#define MK_") else 1
    if len(found) != want:
        sys.exit(f"extract.py: {pattern} found {len(found)} times, expected {want}")
    return "\n".join(found)


def main(qmk, out):
    parts = []
    for name, pieces in PIECES.items():
        src = open(f"{qmk}/{name}", encoding="utf-8").read()
        for kind, what in pieces:
            parts.append(f"// {name}: {what}\n" + (function(src, what) if kind == "func" else lines(src, what)))
    open(out, "w", encoding="utf-8").write("\n\n".join(parts) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
