# TEX Shinobi BLE5: QMK v1.4

Fifth release of the open-source QMK firmware for the **TEX Shinobi BLE5**. Switching Bluetooth hosts now works
the way the stock firmware does it, the installer keeps your settings, and the installer comes for the Mac too.

**Unofficial.** Not TEX firmware, and not supported by TEX. Published with TEX's permission. TEX's bootloader is
never touched: you can flash the stock firmware back at any time with TEX's own `AP_0407_4.04.exe`.

## Downloads

| File | What it is |
|---|---|
| `tex_shinobi_v1.4.bin` | The firmware image, for the installers below, `shinobi/tools/tex_flash.py` (Python 3 and `hidapi`), or the [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/). |
| `tex_flash.exe` | The installer as one Windows file, no Python and no administrator rights needed: `tex_flash.exe tex_shinobi_v1.4.bin`. Not signed, so Windows may warn about an unknown publisher (More info, Run anyway). |
| `tex_flash_macos_arm64` | The same installer for a Mac with Apple silicon (M1 and later). **Not yet tested with a keyboard.** |
| `tex_flash_macos_x86_64` | The same installer for a Mac with an Intel processor. **Not yet tested with a keyboard.** |
| `tex_shinobi_v1.4_updater.exe` | TEX's AP_0407 V1.04.04 updater with this firmware inside in place of the stock image; nothing else in it is changed. Shared with TEX's permission. Run `tex_shinobi_v1.4_updater.exe -force` from a Command Prompt run as administrator. It resets the settings. |
| `SHA256SUMS.txt` | SHA-256 of the files above. |

`tex_shinobi_v1.4.bin` is 28,068 bytes, SHA-256 `5ef2537d5a26c98039be1b5cb38fbd6523227cf4d34211c45d17524768915462`.
The keymap editor knows the release by this hash, so the release must carry exactly this image.

On a Mac, in Terminal, from the folder with both files (use `tex_flash_macos_x86_64` on an Intel Mac):

    chmod +x tex_flash_macos_arm64
    xattr -d com.apple.quarantine tex_flash_macos_arm64
    ./tex_flash_macos_arm64 tex_shinobi_v1.4.bin

The Mac installers are not signed by Apple; `xattr` lets macOS run them.

Turn the computer's Bluetooth off before flashing. Full instructions: [shinobi/README.md](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/README.md#installing). Keys, Fn combinations and
known issues: the [owner's manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md).

## Changed

* **Switching Bluetooth hosts works.** Tap Fn+Mute, Fn+Vol- or Fn+Vol+ and the keyboard reconnects to that
  slot's computer without pairing again. Before, a tap often put the slot into pairing, or did nothing. The light
  blinks slowly while it reconnects, then stays on for 2 seconds once connected, as with the stock firmware.
  Tapping the slot it is already on does nothing. Holding the key for 3 seconds still pairs, and letting go of Fn
  before the slot key no longer turns a tap into a hold.
* **Flashing keeps your settings.** `tex_flash` (the exe, the Mac installers and `tex_flash.py`) now leaves the
  TrackPoint sensitivity, up/down speed, sleep time and Mac layout as they were. `--reset-settings` clears them.
  This works for any firmware flashed with this release's installer, the older ones included. TEX's updater, and
  `tex_flash` from v1.3 and earlier, still reset them.
* **Fn+M** switches the Mac layout (Alt and Win swapped) on or off without the DIP switches, and the keyboard
  remembers it.
* **Fn+B** adds `bl` at the end, for Bluetooth bug reports: link state, slot, and slot taps since power-on, for
  example `bl401` = connected, slot 1, one tap. See the [manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md#what-the-keyboard-types).
* **Installers for the Mac**, Apple silicon and Intel. `tex_flash.exe` and the Mac installers are now built by
  GitHub Actions from the repository, each tested there before it is packaged.

Fn+B's line:

    v1.4 dflt 2026-11-23-15:10:00 bt85% adc3380 aa z15m tp3 ud100 dip24 idl15m34s wk1420ms bl401

## Known limits

As in v1.3.

* **After pulling out the USB cable, switch the keyboard off and on.** Otherwise it doesn't type over Bluetooth,
  although the computer still lists it as connected. TEX's stock firmware does the same, so it comes from the
  hardware or the Bluetooth module, not from this firmware.

In short: battery percentage follows alkaline AA cells (NiMH shows 30-60 % for most of its charge); plugging or
unplugging USB restarts the keyboard; ISO and JIS layouts are untested; DIP switch 6 isn't ported; macros play with
no delays; Fn+B's answers type as on a US layout.

## Tested

TESTED-PLACEHOLDER

Checked off the keyboard (2026-11-23): the image is 28,068 of the 28,076 bytes TEX's bootloader takes, with the
settings record in place; the keymap editor's data for v1.0 to v1.3 is unchanged and v1.4 is added. Host tests of
the input logic pass (`shinobi/test/host/run.sh`), and the installer's 32 tests pass on Windows and on macOS 15.
Built with QMK `f5db962` and arm-none-eabi-gcc 13.2.1, with the build date pinned to `2026-11-23-15:10:00`.
