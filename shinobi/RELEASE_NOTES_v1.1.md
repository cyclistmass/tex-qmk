# TEX Shinobi BLE5: QMK v1.1

Second release of the open-source QMK firmware for the **TEX Shinobi BLE5**. It adds sequence macros and mouse
movement keys, which the [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/) now writes
without a compiler, makes DIP switches 4 and 5 work, and adds DIP, wake and idle readouts to Fn+B.

**Unofficial.** Not TEX firmware, and not supported by TEX. Published with TEX's permission. TEX's bootloader is
never touched: you can flash the stock firmware back at any time with TEX's own `AP_0407_4.04.exe`.

## Downloads

| File | What it is |
|---|---|
| `tex_shinobi_v1.1_updater.exe` | Easiest. TEX's AP_0407 V1.04.04 updater with this firmware inside in place of the stock image; nothing else in it is changed. Shared with TEX's permission. Run `tex_shinobi_v1.1_updater.exe -force` from a Command Prompt. |
| `tex_shinobi_v1.1.bin` | The firmware image, for `shinobi/tools/tex_flash.py` (needs Python 3, `hidapi`, and TEX's `AP_0407_4.04.exe` as the key source), and the image the keymap editor patches. |
| `SHA256SUMS.txt` | SHA-256 of both files. |

`tex_shinobi_v1.1.bin` is 27,704 bytes, SHA-256 `384d81971df6dd6021832dbddf47cc91c2d17c22cd2f0c6d9448a6d14774acb5`.
The keymap editor knows the release by this hash, so the release must carry exactly this image.

Turn the PC's Bluetooth off before flashing. Full instructions: [shinobi/README.md](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/README.md). Keys, Fn combinations and
known issues: the [owner's manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md).

## New

* **Keymap editor** (a web page, also for v1.0): remap any key on the Base, Mac, Fn-Ctrl swap and Fn layers, add
  shortcuts such as Ctrl+C, and download a ready-to-flash image or the `keymap.c`. It changes only the keymap
  bytes, and macro bytes for v1.1, of the released image, and refuses any image it doesn't know.
* **Sequence macros:** keys that type a short phrase or a run of keys (US layout, 96 bytes in all). The editor
  makes Macro 0-15.
* **Mouse movement keys:** up, down, left, right and four diagonals, accelerating while held; the editor has an Fn +
  U I O / J K L / M , preset.
* **DIP switch 4:** hold Fn and push the TrackPoint to scroll; a tap of Fn alone is a middle click.
* **DIP switch 5:** reverses vertical scrolling.
* **Fn+B** also types `dip` (the switches that are on), `idl` (the last stretch with no key or TrackPoint input)
  and `wk` (how long Bluetooth took to come back after the last sleep). The whole line is terser (`zzz15m` for the sleep
  time, also when Fn+F1...F9 types it back, and `tp3` for Fn+1...9). The [manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md#what-the-keyboard-types)
  translates every field:

      v1.1 default 2026-11-12-23:45:00
      bat85% adc2900 aa zzz15m tp3 dip24 idl15m34s wk1420ms

## Fixed

* **The docs described a three-position profile switch.** The keyboard has a block of DIP switches; the README and
  manual now describe switches 1-5 as the firmware reads them (reported by Mauro, fixed in fc903d3).
* **DIP switches 4 and 5 did nothing** in v1.0. They now work as on stock (see New).
* **Fn+B and Fn+1...9 / Fn+F1...F9 let go of a held Shift** (since v1.0): typing their answer released Shift,
  so the next letter came out lower-case although Shift was still down. Typed answers and macros now play with
  the modifiers cleared and give back the ones held, so a held Ctrl or Shift no longer changes a macro either.
* **No keymap or macro tool** (v1.0 known limit): TEX's configurator and macro tool don't work with this firmware;
  the keymap editor replaces them.
* **Keymaps only at build time** (v1.0 known limit): the editor patches the released image, so remapping no longer
  needs a compiler.

## Known limits

* Battery percentage assumes alkaline AA cells; NiMH reads low. The scale waits for voltmeter readings next to
  Fn+B's `adc` value.
* Plugging or unplugging USB restarts the keyboard (a power-on reset on this hardware). Settings are kept.
* ISO and JIS layouts are in the keymap but untested. Reports welcome.
* Flashing v1.1 over the stock firmware hasn't been tested yet with either method; both were tested over earlier
  QMK builds.
* Stock's factory flash self-test is written, as a USB command run by `tools/tex_selftest.py`, but not in this
  build: it is in builds with `TEX_SELFTEST` (88 bytes).
* DIP switch 6 (TEX's file system mode) isn't ported. Switches 7 and 8: stock doesn't read them, and it isn't known
  whether they are wired; Fn+B's `dip` shows what the keyboard sees.
* Sequence macros type a US layout with no delays. Fn+B reports the keymap as `default` in an editor-made image.

## Tested

**Not yet on the keyboard.** Pending before release: flashing v1.1 (over stock and over v1.0), DIP switches 1-5,
the Fn+B readouts, macros and mouse keys over USB and Bluetooth, and an editor-made image.

Checked off the keyboard (2026-11-12): the image is 27,704 of the 28,076 bytes TEX's bootloader takes, with the
settings record in place; two pinned rebuilds give the same SHA-256; the editor's byte-identity test passes for
v1.0 and v1.1 (a patched release equals a compiled build of the exported `keymap.c`, with changed keys, shortcuts,
mouse keys and three macros). Host tests of the input logic pass: mouse keys, DIP 4's Fn scrolling with the
middle button's own key, and macros and typed text with modifiers held, in random press and release sequences
(`shinobi/test/host/run.sh`, also in CI). Built with QMK `f5db962` and arm-none-eabi-gcc 13.2.1, with the build date pinned to
`2026-11-12-23:45:00`.
