# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Write the keymap editor's data file, shinobi/editor/shinobi_data.js, from the sources it depends on.

usage: python -I gen_editor_data.py <qmk_firmware dir> <release image.bin> <release tag> <QMK build date>

Reads, without interpreting key meanings (editor/editor_core.js owns that):
  * <qmk_firmware>/quantum/keycodes.h and quantum_keycodes.h at the pinned commit: keycode names and values, the
    modifier masks and the MO()/TG() bases;
  * qmk/shinobi.h: the board's own keycodes, numbered from QK_KB_0 in enum order;
  * qmk/keyboard.json: the LAYOUT's matrix positions, in argument order;
  * qmk/keymaps/default/keymap.c: the layer names and the default keymap as tokens, and the rest of the file as the
    template the editor exports keymap.c from;
  * the release image: its sha256 and size. The keymaps' place in it is fixed by ld/HT32F52352_TEX_SHINOBI.ld
    (section .tex_keymaps at 0x3800, image base 0x3200); the editor checks those bytes against the default keymap
    before it patches anything.
The physical key positions below are drawn from the key identities (ThinkPad-style rows); keyboard.json's x/y
are matrix order. They place keys on screen only.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHINOBI = os.path.dirname(HERE)
APP_BASE = 0x3200
KEYMAPS_ADDR = 0x3800  # ld/HT32F52352_TEX_SHINOBI.ld, flash0b
MATRIX_ROWS, MATRIX_COLS = 8, 15

# Physical layout by the default base-layer token: (x, y, width), in key units. Approximate.
PHYS = {
    "KC_VOLD": (0, 0, 1), "KC_VOLU": (1, 0, 1), "KC_MUTE": (2, 0, 1), "BLE_PAIR": (3.25, 0, 1),
    "KC_PSCR": (15.5, 0, 1), "KC_SCRL": (16.5, 0, 1), "KC_PAUS": (17.5, 0, 1),
    "KC_ESC": (0, 1.25, 1), "KC_F1": (1.5, 1.25, 1), "KC_F2": (2.5, 1.25, 1), "KC_F3": (3.5, 1.25, 1),
    "KC_F4": (4.5, 1.25, 1), "KC_F5": (5.75, 1.25, 1), "KC_F6": (6.75, 1.25, 1), "KC_F7": (7.75, 1.25, 1),
    "KC_F8": (8.75, 1.25, 1), "KC_F9": (10, 1.25, 1), "KC_F10": (11, 1.25, 1), "KC_F11": (12, 1.25, 1),
    "KC_F12": (13, 1.25, 1), "KC_INS": (15.5, 1.25, 1), "KC_HOME": (16.5, 1.25, 1), "KC_PGUP": (17.5, 1.25, 1),
    "KC_GRV": (0, 2.5, 1), "KC_1": (1, 2.5, 1), "KC_2": (2, 2.5, 1), "KC_3": (3, 2.5, 1), "KC_4": (4, 2.5, 1),
    "KC_5": (5, 2.5, 1), "KC_6": (6, 2.5, 1), "KC_7": (7, 2.5, 1), "KC_8": (8, 2.5, 1), "KC_9": (9, 2.5, 1),
    "KC_0": (10, 2.5, 1), "KC_MINS": (11, 2.5, 1), "KC_EQL": (12, 2.5, 1), "KC_INT3": (13, 2.5, 1),
    "KC_BSPC": (14, 2.5, 1), "KC_DEL": (15.5, 2.5, 1), "KC_END": (16.5, 2.5, 1), "KC_PGDN": (17.5, 2.5, 1),
    "KC_TAB": (0, 3.5, 1.5), "KC_Q": (1.5, 3.5, 1), "KC_W": (2.5, 3.5, 1), "KC_E": (3.5, 3.5, 1),
    "KC_R": (4.5, 3.5, 1), "KC_T": (5.5, 3.5, 1), "KC_Y": (6.5, 3.5, 1), "KC_U": (7.5, 3.5, 1),
    "KC_I": (8.5, 3.5, 1), "KC_O": (9.5, 3.5, 1), "KC_P": (10.5, 3.5, 1), "KC_LBRC": (11.5, 3.5, 1),
    "KC_RBRC": (12.5, 3.5, 1), "KC_BSLS": (13.5, 3.5, 1.5),
    "KC_CAPS": (0, 4.5, 1.75), "KC_A": (1.75, 4.5, 1), "KC_S": (2.75, 4.5, 1), "KC_D": (3.75, 4.5, 1),
    "KC_F": (4.75, 4.5, 1), "KC_G": (5.75, 4.5, 1), "KC_H": (6.75, 4.5, 1), "KC_J": (7.75, 4.5, 1),
    "KC_K": (8.75, 4.5, 1), "KC_L": (9.75, 4.5, 1), "KC_SCLN": (10.75, 4.5, 1), "KC_QUOT": (11.75, 4.5, 1),
    "KC_ENT": (12.75, 4.5, 2.25),
    "KC_LSFT": (0, 5.5, 1.25), "KC_NUBS": (1.25, 5.5, 1), "KC_Z": (2.25, 5.5, 1), "KC_X": (3.25, 5.5, 1),
    "KC_C": (4.25, 5.5, 1), "KC_V": (5.25, 5.5, 1), "KC_B": (6.25, 5.5, 1), "KC_N": (7.25, 5.5, 1),
    "KC_M": (8.25, 5.5, 1), "KC_COMM": (9.25, 5.5, 1), "KC_DOT": (10.25, 5.5, 1), "KC_SLSH": (11.25, 5.5, 1),
    "KC_INT1": (12.25, 5.5, 1), "KC_RSFT": (13.25, 5.5, 1.75),
    "KC_WBAK": (15.5, 5.5, 1), "KC_UP": (16.5, 5.5, 1), "KC_WFWD": (17.5, 5.5, 1),
    "MO(_FN)": (0, 6.5, 1), "KC_LCTL": (1, 6.5, 1.25), "KC_LGUI": (2.25, 6.5, 1.25), "KC_LALT": (3.5, 6.5, 1.25),
    "KC_INT5": (4.75, 6.5, 1), "KC_SPC": (5.75, 6.5, 4.25), "KC_INT2": (10, 6.5, 1), "KC_RALT": (11, 6.5, 1.25),
    "KC_APP": (12.25, 6.5, 1.25), "KC_RCTL": (13.5, 6.5, 1.5),
    "KC_LEFT": (15.5, 6.5, 1), "KC_DOWN": (16.5, 6.5, 1), "KC_RGHT": (17.5, 6.5, 1),
    "MS_BTN1": (6, 7.75, 1.5), "MS_BTN3": (7.5, 7.75, 1.25), "MS_BTN2": (8.75, 7.75, 1.5),
}

LAYER_NAMES = {"_BASE": "Base", "_MAC": "Mac (DIP 2/3)", "_FNCTL": "Fn-Ctrl swap (DIP 1/3)", "_FN": "Fn"}


def fail(msg):
    sys.exit(f"gen_editor_data.py: {msg}")


def parse_keycodes_h(text):
    """Names and values from the generated enums; aliases resolve to the names they repeat."""
    values = {}
    for name, rhs in re.findall(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_]+),", text, re.M):
        if re.fullmatch(r"0x[0-9A-Fa-f]+", rhs):
            values[name] = int(rhs, 16)
        elif rhs in values:
            values[name] = values[rhs]
        else:
            fail(f"keycodes.h: {name} = {rhs} names an unknown keycode")
    return values


def parse_functions(text, values):
    """Modifier masks (QK_LCTL...) and the one-argument keycode macros the editor uses."""
    masks = {m: int(v, 16) for m, v in re.findall(r"^#define (QK_[LR](?:CTL|SFT|ALT|GUI))\s+(0x[0-9A-Fa-f]+)", text, re.M)}
    funcs = {}
    for name in ("LCTL", "LSFT", "LALT", "LGUI", "RCTL", "RSFT", "RALT", "RGUI"):
        m = re.search(rf"^#define {name}\(kc\) \((QK_\w+) \| \(kc\)\)", text, re.M)
        if not m or m.group(1) not in masks:
            fail(f"quantum_keycodes.h: no {name}(kc)")
        funcs[name] = {"base": masks[m.group(1)], "arg": "keycode"}
    for name in ("MO", "TG"):
        m = re.search(rf"^#define {name}\(layer\) \((QK_\w+) \| \(\(layer\) & 0x1F\)\)", text, re.M)
        if not m or m.group(1) not in values:
            fail(f"quantum_keycodes.h: no {name}(layer)")
        funcs[name] = {"base": values[m.group(1)], "arg": "layer"}
    return funcs


def parse_custom(text, values):
    """shinobi.h's enum shinobi_keycodes: the first is QK_KB_0, the rest count up."""
    body = re.search(r"enum shinobi_keycodes \{(.*?)\};", text, re.S)
    if not body:
        fail("shinobi.h: no enum shinobi_keycodes")
    names = []
    for line in re.sub(r"//[^\n]*", "", body.group(1)).split(","):
        line = line.strip()
        if line:
            names.append(line)
    first = re.fullmatch(r"(\w+)\s*=\s*QK_KB_0", names[0])
    if not first:
        fail("shinobi.h: the first keycode is not QK_KB_0")
    names[0] = first.group(1)
    out = {}
    for i, n in enumerate(names):
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", n):
            fail(f"shinobi.h: unexpected enum entry {n!r}")
        out[n] = values["QK_KB_0"] + i
    return out


def split_args(s):
    """Top-level comma split of a LAYOUT(...) body, without comments."""
    s = re.sub(r"//[^\n]*", "", s)
    args, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return [re.sub(r"\s+", "", a) for a in args]


def parse_keymap_c(text, nkeys):
    m = re.search(r"enum layers \{([^}]*)\};", text)
    if not m:
        fail("keymap.c: no enum layers")
    layers = [x.strip() for x in m.group(1).split(",") if x.strip()]
    default, template, pos = {}, "", 0
    for lm in re.finditer(r"\[(\w+)\] = LAYOUT\(", text):
        name = lm.group(1)
        start = lm.end()
        depth, i = 1, start
        while depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        tokens = split_args(text[start:i - 1])
        if len(tokens) != nkeys:
            fail(f"keymap.c: layer {name} has {len(tokens)} keys, keyboard.json {nkeys}")
        default[name] = tokens
        template += text[pos:start] + "@@" + name + "@@"
        pos = i - 1
    template += text[pos:]
    if sorted(default) != sorted(layers):
        fail("keymap.c: the LAYOUT layers do not match enum layers")
    template = template.replace(
        "// Generated by gen_qmk.py from the stock AP_0407 V1.04.04 tables; edit by hand from here on.",
        "// Exported by the TEX Shinobi keymap editor (shinobi/editor). The layer comments describe the stock layout.")
    return layers, default, template


def main():
    if len(sys.argv) != 5:
        fail(__doc__.strip().splitlines()[2])
    qmk_dir, release_bin, tag, build_date = sys.argv[1:]
    read = lambda p: open(p, encoding="utf-8").read()
    values = parse_keycodes_h(read(os.path.join(qmk_dir, "quantum", "keycodes.h")))
    funcs = parse_functions(read(os.path.join(qmk_dir, "quantum", "quantum_keycodes.h")), values)
    custom = parse_custom(read(os.path.join(SHINOBI, "qmk", "shinobi.h")), values)
    clash = sorted(set(custom) & set(values))
    if clash:
        fail(f"shinobi.h keycodes shadow QMK names: {clash}")
    kb = json.load(open(os.path.join(SHINOBI, "qmk", "keyboard.json"), encoding="utf-8"))
    matrix = [k["matrix"] for k in kb["layouts"]["LAYOUT"]["layout"]]
    layers, default, template = parse_keymap_c(read(os.path.join(SHINOBI, "qmk", "keymaps", "default", "keymap.c")),
                                               len(matrix))
    keys = []
    for i, (r, c) in enumerate(matrix):
        tok = default["_BASE"][i]
        if tok not in PHYS:
            fail(f"no physical position for base key {tok}")
        x, y, w = PHYS[tok]
        keys.append({"matrix": [r, c], "x": x, "y": y, "w": w})
    if len(PHYS) != len(matrix):
        fail(f"{len(PHYS)} physical positions for {len(matrix)} keys")
    img = open(release_bin, "rb").read()
    commit = read(os.path.join(SHINOBI, "qmk_firmware.commit")).strip()
    data = {
        "generated_by": "shinobi/tools/gen_editor_data.py",
        "qmk_commit": commit,
        "release": {
            "tag": tag,
            "file": os.path.basename(release_bin),
            "size": len(img),
            "sha256": hashlib.sha256(img).hexdigest(),
            "build_date": build_date,
            "keymaps_offset": KEYMAPS_ADDR - APP_BASE,
        },
        "matrix": {"rows": MATRIX_ROWS, "cols": MATRIX_COLS},
        "layers": [{"id": l, "name": LAYER_NAMES.get(l, l)} for l in layers],
        "keys": keys,
        "default_layers": default,
        "keycodes": values,
        "custom_keycodes": custom,
        "functions": funcs,
        "keymap_c_template": template,
    }
    out = os.path.join(SHINOBI, "editor", "shinobi_data.js")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// Generated by shinobi/tools/gen_editor_data.py; do not edit.\n")
        f.write("globalThis.SHINOBI_DATA = ")
        json.dump(data, f, indent=None, separators=(",", ":"))
        f.write(";\n")
    print(f"{out}: {len(keys)} keys, {len(layers)} layers, {len(values)} QMK keycodes, {len(custom)} board keycodes")


if __name__ == "__main__":
    main()
