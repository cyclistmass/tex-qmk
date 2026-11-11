# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate the TEX Shinobi QMK layout and default keymap from the stock AP_0407 tables.

usage: python -I gen_qmk.py <decrypted_base3200.bin> <keyboard_dir>

Tables (all observed in the decrypted app image, base 0x3200):
  0x9DCB  base keymap, 14 cols x 8 rows, index col*8+row
  0x9E5A  Mac swap pairs (profiles 2/3), plain codes
  0x9E62  Fn pairs whose targets are firmware actions (flag 1)
  0x9E7C  Fn pairs whose targets are plain codes (flag 0)
"""
import json
import os
import sys

BASE = 0x3200
ROWS, COLS = 8, 14
POS_FN = 48       # stock default Fn position (col 6 row 0), code 0xCB underneath
POS_FN2 = 70      # stock also overlays Fn on col 8 row 6 (code 0xC9, middle button)
POS_CTRL = 0      # LCtrl; profiles 1/3 move Fn here and 0xCB becomes LCtrl

HID = {0x28: "KC_ENT", 0x29: "KC_ESC", 0x2A: "KC_BSPC", 0x2B: "KC_TAB", 0x2C: "KC_SPC", 0x2D: "KC_MINS",
       0x2E: "KC_EQL", 0x2F: "KC_LBRC", 0x30: "KC_RBRC", 0x31: "KC_BSLS", 0x33: "KC_SCLN", 0x34: "KC_QUOT",
       0x35: "KC_GRV", 0x36: "KC_COMM", 0x37: "KC_DOT", 0x38: "KC_SLSH", 0x39: "KC_CAPS", 0x46: "KC_PSCR",
       0x47: "KC_SCRL", 0x48: "KC_PAUS", 0x49: "KC_INS", 0x4A: "KC_HOME", 0x4B: "KC_PGUP", 0x4C: "KC_DEL",
       0x4D: "KC_END", 0x4E: "KC_PGDN", 0x4F: "KC_RGHT", 0x50: "KC_LEFT", 0x51: "KC_DOWN", 0x52: "KC_UP",
       0x64: "KC_NUBS", 0x65: "KC_APP", 0x87: "KC_INT1", 0x88: "KC_INT2", 0x89: "KC_INT3", 0x8A: "KC_INT4",
       0x8B: "KC_INT5", 0xE0: "KC_LCTL", 0xE1: "KC_LSFT", 0xE2: "KC_LALT", 0xE3: "KC_LGUI", 0xE4: "KC_RCTL",
       0xE5: "KC_RSFT", 0xE6: "KC_RALT", 0xE7: "KC_RGUI"}
HID.update({0x04 + i: f"KC_{chr(ord('A') + i)}" for i in range(26)})
HID.update({0x1E + i: f"KC_{(i + 1) % 10}" for i in range(10)})
HID.update({0x3A + i: f"KC_F{i + 1}" for i in range(12)})
# Unflagged 0xEC..0xFD index the 18-bit consumer bitmap of HID report 2 (descriptor at 0x9BD5).
CONSUMER = ["KC_MSEL", "KC_MAIL", "KC_CALC", "KC_MYCM", "KC_MPLY", "KC_MSTP", "KC_MPRV", "KC_MNXT", "KC_MUTE",
            "KC_VOLD", "KC_VOLU", "KC_WSCH", "KC_WHOM", "KC_WBAK", "KC_WFWD", "KC_WSTP", "KC_WREF", "KC_WFAV"]
HID.update({0xEC + i: k for i, k in enumerate(CONSUMER)})
# TEX codes that FUN_5658 turns into mouse buttons (0xC8 left, 0xCA right, 0xC9 middle).
HID.update({0xC8: "MS_BTN1", 0xCA: "MS_BTN2", 0xC9: "MS_BTN3"})

# Flagged Fn targets handled by FUN_5574.
ACTIONS = {0x31 + i: f"TP_SEN{i + 1}" for i in range(9)}
ACTION_NOTES = {0x8A: "stock: BLE slot 1 [I]", 0x8B: "stock: BLE slot 2 [I]", 0x8C: "stock: BLE slot 3 [I]",
                0x8D: "stock: action 0x8D, unknown"}


def main():
    img_path, out_dir = sys.argv[1], sys.argv[2]
    img = open(img_path, "rb").read()

    def at(addr, n):
        return img[addr - BASE:addr - BASE + n]

    km = at(0x9DCB, ROWS * COLS)
    mac = list(zip(at(0x9E5A, 8)[0::2], at(0x9E5A, 8)[1::2]))
    fn_act = list(zip(at(0x9E62, 0x1A)[0::2], at(0x9E62, 0x1A)[1::2]))
    fn_code = list(zip(at(0x9E7C, 10)[0::2], at(0x9E7C, 10)[1::2]))
    print("mac", [(hex(a), hex(b)) for a, b in mac])
    print("fn actions", [(hex(a), hex(b)) for a, b in fn_act])
    print("fn codes", [(hex(a), hex(b)) for a, b in fn_code])

    keys = [(r, c) for r in range(ROWS) for c in range(COLS) if km[c * 8 + r]]
    code = {(r, c): km[c * 8 + r] for r, c in keys}
    pos = {(r, c): c * 8 + r for r, c in keys}

    def base_kc(rc):
        if pos[rc] == POS_FN:
            return "MO(_FN)"
        return HID.get(code[rc], "KC_NO")

    base = {rc: base_kc(rc) for rc in keys}
    unknown = sorted(hex(code[rc]) for rc in keys if base[rc] == "KC_NO")

    mac_l = {rc: "_______" for rc in keys}
    for src, dst in mac:
        for rc in keys:
            if code[rc] == src:
                mac_l[rc] = HID[dst]

    fnctl = {rc: "_______" for rc in keys}
    for rc in keys:
        if pos[rc] == POS_CTRL:
            fnctl[rc] = "MO(_FN)"
        elif pos[rc] == POS_FN:
            fnctl[rc] = "KC_LCTL"

    fn = {rc: "_______" for rc in keys}
    notes = {}
    for src, dst in fn_act:
        for rc in keys:
            if code[rc] == src:
                if dst in ACTIONS:
                    fn[rc] = ACTIONS[dst]
                else:
                    notes[rc] = ACTION_NOTES.get(dst, f"stock: action {dst:#x}")
    for src, dst in fn_code:
        for rc in keys:
            if code[rc] == src:
                fn[rc] = HID[dst]

    # keyboard.json: matrix-ordered coordinates until the physical layout is confirmed.
    kb = {
        "manufacturer": "TEX",
        "keyboard_name": "Shinobi",
        "maintainer": "mauro",
        "url": "https://tex.com.tw/products/shinobi",
        "usb": {"vid": "0x04D9", "pid": "0x0407", "device_version": "9.0.0"},
        "build": {"lto": True},
        "eeprom": {"driver": "transient"},
        "features": {"bootmagic": True, "mousekey": True, "extrakey": True, "nkro": True},
        "bootmagic": {"matrix": [4, 8]},
        "ps2": {"enabled": True, "mouse_enabled": True, "driver": "busywait", "clock_pin": "B3", "data_pin": "B5"},
        "indicators": {"caps_lock": "C10", "on_state": 0},
        "diode_direction": "COL2ROW",
        "matrix_pins": {
            "rows": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"],
            "cols": ["D2", "B8", "B11", "D0", "B13", "B14", "A15", "A14", "A10", "C14", "C15", "B15", "C0", "A11",
                     "C13"],
        },
        "layouts": {"LAYOUT": {"layout": [
            {"label": base[rc], "matrix": [rc[0], rc[1]], "x": rc[1], "y": rc[0]} for rc in keys]}},
    }
    with open(os.path.join(out_dir, "keyboard.json"), "w", newline="\n") as f:
        json.dump(kb, f, indent=4)
        f.write("\n")

    def layer(name, m, comment):
        w = max(len(v) for v in m.values()) + 1
        lines = [f"    // {comment}", f"    [{name}] = LAYOUT("]
        for r in range(ROWS):
            row = [m[rc] for rc in keys if rc[0] == r]
            last = r == ROWS - 1
            text = ", ".join(k.ljust(w - 1) for k in row).rstrip()
            lines.append(f"        {text}{'' if last else ','}")
        lines.append("    ),")
        return lines

    fn_notes = "; ".join(f"row {rc[0]} col {rc[1]} ({base[rc]}) {n}" for rc, n in sorted(notes.items()))
    out = [
        "// Copyright 2026 Mauro DiBenedetto",
        "// SPDX-License-Identifier: GPL-2.0-or-later",
        "// Generated by gen_qmk.py from the stock AP_0407 V1.04.04 tables; edit by hand from here on.",
        "// LAYOUT is in matrix order (one line per matrix row, columns 0-13, empty positions skipped).",
        "#include QMK_KEYBOARD_H",
        "",
        "enum layers { _BASE, _MAC, _FNCTL, _FN };",
        "",
        "// clang-format off",
        "const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {",
        *layer("_BASE", base, "Stock base table 0x9DCB. Fn sits on matrix position 48 like stock; stock also puts Fn "
                              "on position 70, which QMK keeps as the middle button."),
        *layer("_MAC", mac_l, "Stock Mac swap 0x9E5A (profiles 2 and 3)."),
        *layer("_FNCTL", fnctl, "Profiles 1 and 3 move Fn to position 0 and turn position 48 into LCtrl."),
        *layer("_FN", fn, "Stock Fn tables 0x9E62/0x9E7C. Not ported: " + (fn_notes or "nothing") + "."),
        "};",
        "// clang-format on",
        "",
        "// Stock profile defaults (FUN_4948): 0 = default, 1 = Fn/Ctrl swapped, 2 = Mac, 3 = Mac + Fn/Ctrl swapped.",
        "void profile_switch_user(uint8_t profile) {",
        "    if (profile == 1 || profile == 3) {",
        "        layer_on(_FNCTL);",
        "    } else {",
        "        layer_off(_FNCTL);",
        "    }",
        "    if (profile == 2 || profile == 3) {",
        "        layer_on(_MAC);",
        "    } else {",
        "        layer_off(_MAC);",
        "    }",
        "}",
        "",
    ]
    kdir = os.path.join(out_dir, "keymaps", "default")
    os.makedirs(kdir, exist_ok=True)
    with open(os.path.join(kdir, "keymap.c"), "w", newline="\n") as f:
        f.write("\n".join(out))
    print("keys", len(keys), "unknown codes", unknown)


if __name__ == "__main__":
    main()
