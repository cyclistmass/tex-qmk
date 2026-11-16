# TEX Shinobi BLE5: QMK v1.2

Third release of the open-source QMK firmware for the **TEX Shinobi BLE5**. A second TrackPoint tune sets up/down
speed against left/right (Fn -, Fn =, Fn+0). Fn+B's line is shorter, and it says
whether the keymap is the built-in one or one changed with the
[keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/).

**Unofficial.** Not TEX firmware, and not supported by TEX. Published with TEX's permission. TEX's bootloader is
never touched: you can flash the stock firmware back at any time with TEX's own `AP_0407_4.04.exe`.

## Downloads

| File | What it is |
|---|---|
| `tex_shinobi_v1.2_updater.exe` | Easiest. TEX's AP_0407 V1.04.04 updater with this firmware inside in place of the stock image; nothing else in it is changed. Shared with TEX's permission. Run `tex_shinobi_v1.2_updater.exe -force` from a Command Prompt run as administrator (Windows asks for administrator rights for TEX's updater). |
| `tex_flash.exe` | New. The installer as one Windows file, no Python needed and no administrator rights: `tex_flash.exe tex_shinobi_v1.2.bin`, or an image from the keymap editor. TEX's key is built in, published with TEX's permission. Not signed, so Windows may warn about an unknown publisher (More info, Run anyway). |
| `tex_shinobi_v1.2.bin` | The firmware image, for `tex_flash.exe` or `shinobi/tools/tex_flash.py` (Python 3 and `hidapi`; nothing from TEX needed any more), and the image the keymap editor patches. |
| `SHA256SUMS.txt` | SHA-256 of the three files. |

`tex_shinobi_v1.2.bin` is 28,048 bytes, SHA-256 `a8e34054b47fb229ca5691d06efcf887dff13d8ab883f9b6d311bab101b0ada0`.
The keymap editor knows the release by this hash, so the release must carry exactly this image.

After pulling out the USB cable, switch the keyboard off and on before using Bluetooth (stock firmware too).

Turn the PC's Bluetooth off before flashing. Full instructions: [shinobi/README.md](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/README.md). Keys, Fn combinations and
known issues: the [owner's manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md).

## Changed

* **The installer needs nothing from TEX.** `tex_flash.py` has TEX's firmware key built in (published with TEX's
  permission), and the release adds `tex_flash.exe`, the same installer as one Windows file. It also stops with a
  message if TEX's updater window is open, which used to leave the keyboard in the bootloader.
* **Battery level from meter readings.** Up to v1.1 the battery scale was a guess and read about 27 % high: nearly
  flat NiMH cells (2.32 V) showed 95 %. v1.2 uses a scale set from voltmeter readings, and the LED's low-battery
  blinks start at 1.10 V a cell (before, only near 0.86 V). The percentages follow alkaline cells, so NiMH
  rechargeables show 30-60 % for most of their charge.
* **TrackPoint up/down against left/right.** Fn - makes up/down a step slower, Fn = a step faster, Fn+0 the same
  as left/right again: 50 % to 200 % in 16 steps. For a stick whose up/down feels faster than sideways, or a
  portrait screen. Scrolling is unchanged. The keys type back `tp3 ud90` and so on, Fn+1...9 now type
  `tp3 ud100`, and Fn+B adds `ud100`. Saved with the other settings. Flashing any firmware, this one included, resets the settings to
  the defaults. In the keymap editor the three keys are under "TrackPoint up/down against left/right".
* **Fn+B names the keymap `dflt` or `cust`.** `dflt` is the built-in keymap; `cust` means the keymap editor
  changed keys or added macros (v1.1 said `default` either way). The editor marks its images with one byte after
  the macro table, so macros now share 95 bytes instead of 96.
* **Shorter labels:** `bt` for the battery level (was `bat`) and `z` for the sleep time (was `zzz`), also when
  Fn+F1...F9 types it back (`z15m`, `z never`). The rest of the line is as in v1.1:

      v1.2 dflt 2026-11-13-14:00:00 bt85% adc3380 aa z15m tp3 ud100 dip24 idl15m34s wk1420ms

  The [manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md#what-the-keyboard-types)
  translates every field.

## Known limits

As in v1.1, except that Fn+B no longer reports an editor-made keymap as `default`.

* **After pulling out the USB cable, switch the keyboard off and on.** Otherwise it doesn't type over Bluetooth,
  although the computer still lists it as connected. TEX's stock firmware does the same (checked 2026-11-15, as
  were v1.1 and v1.2), so it comes from the hardware or the Bluetooth module, not from this firmware.

In short: battery percentage
follows alkaline AA cells (NiMH shows 30-60 % for most of its charge); plugging or unplugging USB restarts the keyboard; ISO and JIS layouts
are untested; DIP switch 6 isn't ported; macros play with no delays; Fn+B's answers type as on a US layout.

## Tested

On one keyboard (US ANSI, two NiMH AA cells), 2026-11-15: three flashes with the one-file `tex_flash.exe`
(over v1.1 with an editor-made keymap, and over v1.2 both ways), each with the bootloader's checksum matching
and the keyboard back about a second later; the Fn+B line with the built-in keymap (`dflt`) and with an
editor-made image (`cust`, Caps Lock as Esc, which typed Esc); typing over USB and over Bluetooth after a power
cycle; Fn - down to `ud90` and Fn = back, with the answers typed back; `ud90` kept through a power cut; the
battery line on battery (`bt87% adc3423`) against meter readings.

Not tested on the keyboard: flashing over the stock firmware, the updater exe for v1.2, Fn+0, the ends of
the up/down range, scrolling with the up/down tune set, and DIP switches 4 and 5. Bluetooth stops after a USB
unplug until the keyboard is switched off and on, as with stock (above).

Checked off the keyboard (2026-11-13): the image is 28,048 of the 28,076 bytes TEX's bootloader takes, with the
settings record in place; the editor's byte-identity test passes for v1.0, v1.1 and v1.2 (for v1.2 a patched image,
`cust` byte included, equals a compiled build of the exported `keymap.c`); the editor refuses a v1.2 image whose
`cust` byte is already set, and sets it for one changed key or one macro alone. Host tests of the input logic (now
also the up/down scaling) and the linked signed division pass (`shinobi/test/host/run.sh`, `shinobi/test/host/div_asm.sh`, also in CI). Built
with QMK `f5db962` and arm-none-eabi-gcc 13.2.1, with the build date pinned to `2026-11-13-14:00:00`.
