# Keymap editor: design note (proposal, 2026-11-11)

TEX's configurator and macro tool used the stock vendor commands 0x40-0x7C, which QMK does not implement. VIA and Vial
don't fit, because the IAP takes images up to 28,076 bytes and v1.0 is 28,072. This note proposes a replacement that
needs no C and no toolchain.

## What TEX's tools offered, and what this editor does instead

TEX had two configuration paths, and they differ:

* **TEX's web configurator**, at `program.tex.com.tw/shinobi/` (the Shinobi manual gives the older address
  `shinobi.tex-design.com.tw`). It builds a `.TEX` file, and the owner copies that file onto the keyboard in
  USB-disk mode (DIP port 6). This is TEX's documented tool. A research agent read its HTML and `build/tex.js` as
  text and ran none of it. The manuals are in `~/Documents/manuals/tex/shinobi/` (`Shinobi_A5.pdf`,
  `BLE_5.0_User_manual.pdf`).
* **The BLE5 firmware's own HID config commands**, `0x40-0x7C` in `FUN_6d60` (`firmware_ghidra_decompile.c` in
  `Downloads/AP_0407_4.04/analysis`). This is what our board's stock firmware actually stores. No public tool for it
  was found.

Tags: [T] stated by TEX (page or manual), [C] read from the configurator's code, [O] read from the stock firmware,
[I] inferred.

| TEX feature | Source | Here |
|---|---|---|
| Remap every key, on every layer | [T]: Top and FN1-FN3 layers, all editable. [O]: 5 layers × 112 matrix positions, 10-bit codes (`51 20` / `51 21`, `FUN_5e44`) | **Covered** on QMK's 4 layers |
| 3 profiles with their own keymaps | [T]: DIP ports 1/2/3 pick profiles 1-3 when a `.TEX` file is loaded. [O]: one 0x340-byte block per profile, `50 20 n` | **Adapted:** DIP switches 1-3 turn the Fn-Ctrl and Mac overlay layers on or off (MANUAL.md), and both overlays are editable. Three full keymaps would need 3 × 960 bytes |
| FN1-FN3 keys, up to 4 positions each | [T], [C] | **Adapted:** `MO()` / `TG()` keys anywhere, for the Fn layer and the two overlays. There is no FN2 or FN3 layer, because the keymap space holds 4 layers |
| Disable a key | [T] | **Covered** (`KC_NO`) |
| Letters, symbols, ISO/JIS keys, regional label sets (UK, FR, DE, SP, RU, NOR) | [T] | **Covered.** The keycodes are the same; the editor offers the same label sets |
| Media keys: play, stop, previous, next, mute, volume | [T] | **Covered** (extrakey is on) |
| App keys: Mail, Calculator, My Computer, Back, Forward | [T] | **Covered** (extrakey) |
| F13-F24 | [T] | **Covered** |
| Mouse left, right and middle click | [T] | **Covered** (`tp_buttons`) |
| Mouse buttons 4 and 5, and pointer movement from keys (8 directions) | [T] | **Not possible:** mousekey is compiled out for size |
| TrackPoint speed 1-9 | [T] | **Covered** (`TP_SEN1-9`) |
| TrackPoint speed −/+ | [T] | **Not in v1.0.** It needs a few bytes of code |
| Macros: 12 (M1-M12), up to 15 steps each, each step a chord of up to 5 keys, fixed timing | [T] 12 macros; [C] 15 steps, 5-key limit, timing value 128, not editable | **Adapted (v1.1):** 16 macros sharing about 100 bytes, 1 byte per key, modifiers held for the next key. The 12 × 15 maximum does not fit |
| Mouse and TrackPoint keycodes inside macros | [C] | **Not possible** in the budget |
| Firmware-level macros: 24 slots, per-event delays, mouse movement, repeat once / N times / until stopped, 4 KB | [O] (`51 18`, `44 xx`, `FUN_8698`); no tool for them was found | **Not possible** in the budget, beyond one optional fixed delay code |
| Reset to default | [T] | **Covered:** "Reset" in the editor, or flash the release image |
| Save the configuration online (Firebase sign-in) | [C] | **Adapted:** the owner keeps `keymap.json`. No accounts |
| Changes without a firmware flash (`.TEX` file copy, or HID writes) | [T], [O] | **Not possible:** 4 bytes free, so every change is a reflash |
| DIP-port features: Mouse_Fn dual function, reverse scroll, USB-disk mode | [T] | Not editor features; the QMK port's behaviour is in MANUAL.md |
| Hidden settings: TrackPoint sensitivity, scroll direction, debounce, key repeat, LED timeout | [C]: hidden in TEX's page and not written to the file | Out of scope |

Not found: the BLE5 configurator itself, which TEX's download page doesn't list. The meaning of CODE150 and "Lan1"
in TEX's key list is unknown. QMK reads DIP switches 1-3 (matrix column 14) the way stock does without a `.TEX`
file. MANUAL.md notes that this is untested on the keyboard.

## Measured budget (v1.0 ELF, `arm-none-eabi-size` and the link map)

| Region | Size | Used | Free |
|---|---|---|---|
| flash0 `0x3200-0x37FF` (vectors, unwind table, `.data` image) | 1,536 | 1,424 | **112** |
| flash0b `0x3800-0x3BF7` (`keymaps[4][8][15]`, uint16) | 1,016 | 960 | **56** |
| flash2 from `0x3C04` (code, constants) up to the 28,076-byte limit | | | **4** |

The keymaps array sits at a fixed address, 0x3800, in a section of its own. A remap only changes keycode values.
The array keeps its size and nothing else in the image moves, so the size check always passes. The record at 0x3BF8
is not touched either.

## 1. UI: a static web page

A single HTML file, `shinobi/editor/index.html`, with no install and no server. It is served from the existing
GitHub Pages site and also works when opened from disk.

* It draws the board with the physical layout. `keyboard.json`'s x/y are in matrix order, not physical positions,
  and PORT_NOTES lists the real coordinates as an open question. I'd draw the layout from the key identities
  (ThinkPad-style rows, TrackPoint buttons, the arrow cluster with Back/Forward). **Mauro checks it against the
  board.**
* Tabs for Base, Mac, Fn-Ctrl swap and Fn. Click a key, then pick from a vetted list: letters and symbols,
  modifiers, F-keys, navigation, media, mouse buttons 1-3, MO/TG layer keys, the Shinobi keys (BLE slots, TP_SEN,
  SLEEP, BAT_REPORT), shortcuts such as Ctrl+C or Ctrl+Shift+Esc, and macros M0-Mn. Keycodes for features that are
  compiled out (mousekey movement, send_string, tap-dance) are not offered.
* It saves and loads a `keymap.json`, the owner's editable source, and exports the result (section 2).

A desktop app gains nothing over this, and it would need packaging and signing.

## 2. Build path: patch the release image (recommended), with C export for builders

**Recommended: no compiler at all.** The page loads the released `.bin` (downloaded, or bundled from the release).
It checks it against a small manifest that CI writes at release time: the image sha256, the keymaps offset and
size from the link map, and the default keymap bytes. It then writes the new keycodes over the 960 bytes at
0x3800 and offers `tex_shinobi_custom.bin` for download. It fails closed: the image hash must match the manifest,
and the bytes at the offset must equal the default keymap, before anything is patched.

* Owners need no GitHub account, no WSL, no Actions run, and get the result instantly.
* The keycode numbers come from the pinned QMK commit's headers, through a generator script with the values
  checked in. They are not typed by hand.
* **Proof:** a test builds the same keymap through `build_firmware.sh` as C (`gen_keymap.py keymap.json` →
  `keymaps/<name>/keymap.c`) and requires the result to be **byte-identical** to the patched image. That is the
  "build a changed keymap and check the image" acceptance test. If the bytes differ anywhere outside 0x3800-0x3BBF,
  patching is unsafe for that release and the page refuses it.

**Also provided:** the same `gen_keymap.py` writes `shinobi/qmk/keymaps/<name>/keymap.c` for people who build. A
`workflow_dispatch` input on the build workflow can take a keymap folder name, for forks. That path needs a GitHub
account or the ARM toolchain, so it is not the default for owners.

**Flashing does not change.** `tex_flash.py tex_shinobi_custom.bin AP_0407_4.04.exe`, or
`build_updater.py AP_0407_4.04.exe tex_shinobi_custom.bin out/`, which gives an updater exe to run with `-force`.
Flashing from the page over WebHID would be possible later, but it would be a second implementation of the flash
protocol, so it is out of scope here.

## 3. Macros

The table below lists what each kind of macro costs.

| Kind | Example | Cost | Needs |
|---|---|---|---|
| **Shortcut** (one key with modifiers) | Ctrl+C, Win+L, Ctrl+Shift+Esc | 0 bytes (QMK `LCTL(KC_C)` keycodes) | v1.0, patchable today |
| **Sequence** (keys typed in order) | `Ctrl+A Ctrl+C`, a short word, an email address | ~60 bytes of player code + 1 byte per key | firmware v1.1 |

The sequence format is one byte per HID usage. 0xE0-0xE7 are modifiers, which stay held until the next ordinary
key has been tapped, so `E1 0B 08` types "He". 0x00 ends a macro. Keycodes M0-M15 play macro n through the existing
`type_event` (power.c), which already flushes each event correctly over USB and BLE.

**Room for sequences.** v1.1 would put the player code and a fixed-address macro table into the free space in
flash0 and flash0b (168 bytes), through a linker section. flash2 is not touched. That leaves **about 100 bytes of
macro keys in total**, which is enough for a few short sequences, not paragraphs. Once the table has a fixed
address, sequences become patchable too. Getting more room would mean trimming firmware code. One candidate is
`__udivmoddi4` (408 bytes of 64-bit division pulled in somewhere), but that is separate work and needs its own
measurement.

Left out, because they don't fit: editable delays, recording, repeat modes, mouse steps, and per-profile macro sets.

## Proposed order of work

1. `gen_keymap.py` (`keymap.json` ↔ `keymap.c`) and a keycode table from the pinned QMK, with tests.
2. CI writes the manifest next to each `.bin`, and a test checks that the compiled image equals the patched one.
3. The editor page: layout, layers, shortcuts, patch and download. **This gives owners remapping on v1.0.**
4. Firmware v1.1: the macro player and table in the free space. Size checked, flash-tested by Mauro before any
   release.

## Decisions for Mauro

* A web page on GitHub Pages, not a desktop app.
* Patching the release image as the main path, with C export and CI as a secondary path.
* Shortcuts now, and sequence macros in a v1.1 firmware with about 100 bytes of room.
* The physical layout drawn by me, to be checked on the board.
