# QMK firmware for the TEX Shinobi BLE5

Open-source [QMK](https://qmk.fm) firmware for the TEX Shinobi BLE5, the 7-row ThinkPad-style keyboard with a
TrackPoint. It is a full replacement for the stock firmware (AP_0407 V1.04.04). It supports USB, Bluetooth with
three hosts, the TrackPoint, battery sleep, and settings that survive a power cut.

**Unofficial.** This is not TEX firmware, and TEX does not support it. It is published with TEX's permission, and
thanks to TEX for sharing the schematic and answering questions. Install it at your own risk. TEX's bootloader is
never touched, so you can always go back to the stock firmware (see [Going back to stock](#going-back-to-stock)).

The **[owner's manual](MANUAL.md)** covers every key and light, Bluetooth, sleep, troubleshooting and known issues.

Status: v1.0, in daily use on one Shinobi BLE5 (US layout) over USB and Bluetooth since 2026-11-04.

## What works

* All keys, DIP switches 1-3 on the bottom (Fn/Ctrl swap, Mac layout, both) and the Fn layer, taken from the
  stock firmware's own tables.
* TrackPoint with stock sensitivity levels, middle-button scrolling, and a fix for the stock slow-wake bug.
* Bluetooth: three hosts, pairing, and the battery level reported to the host.
* Sleep on battery after an idle time you choose. Key presses wake it.
* Caps Lock LED, low-battery blink, and the pairing blink.
* TEX's updater still recognises the keyboard. You can flash stock firmware back with it at any time.

## Fn keys

| Keys | Does |
|---|---|
| Fn+Mute / Fn+Vol- / Fn+Vol+ | Bluetooth host 1 / 2 / 3. Hold 3 s to pair a new host to that slot |
| Fn+Esc | back to USB |
| Fn+1 ... Fn+9 | TrackPoint sensitivity 1-9; the keyboard types back "tp N" (default 3) |
| Fn+F1 ... Fn+F9 | sleep on battery after 1, 2, 5, 10, 15, 30, 60, 120 min or never; typed back (default 15 min) |
| Fn+B | types the firmware version, then a line with the battery level, power source, sleep time and TrackPoint level |
| Fn+arrows | media keys: Stop, Play, Previous, Next |

The TrackPoint level and sleep time are saved in flash. They survive a power cut, and every USB plug or unplug is
a power cut on this keyboard.

## Installing

You need a Windows PC and the USB cable. **Turn the PC's Bluetooth off before flashing** (Settings > Bluetooth &
devices), so the PC only talks to the keyboard over USB. Downloads are on the
[Releases](https://github.com/cyclistmass/tex-qmk/releases) page. Each release lists SHA-256 sums.

### Option 1: TEX's updater (no other software needed)

`tex_shinobi_v1.0_updater.exe` is TEX's AP_0407 V1.04.04 updater with this firmware inside it in place of the
stock image. Nothing else in the updater is changed. TEX allowed sharing it.

1. Open a Command Prompt in the folder with the exe.
2. Run `tex_shinobi_v1.0_updater.exe -force`.
   `-force` is needed because the updater still shows the stock version number and would otherwise say there is
   nothing to update.
3. Click through the update window as for a normal TEX update. The keyboard switches to its bootloader (USB
   04D9:1407) for about 10 seconds, then comes back as the keyboard (04D9:0407).
4. Press Fn+B. The keyboard types `v1.0 default ...` and a battery line.

### Option 2: the Python flasher

Needs Python 3, `pip install hidapi`, the `tools` folder from this repository, the firmware
`tex_shinobi_v1.0.bin`, and a key. The key can come from either of these:

* TEX's own stock updater, `AP_0407_4.04.exe`, from TEX's download page. It is the key source: the flasher reads
  the key out of it.
* A 52-byte key file, if you have one. `python tools/tex_key.py AP_0407_4.04.exe xor_key_52.bin` writes one.

From the `tools` folder:

    python tex_flash.py tex_shinobi_v1.0.bin AP_0407_4.04.exe

It takes about 5 seconds. It switches the keyboard to the bootloader, keeps a copy of the version block, writes
the image, checks the bootloader's checksum, and restarts the keyboard. "the app is up (04D9:0407)" means
success. If any step fails, it stops and the keyboard stays in the bootloader, ready for another try or for TEX's
updater.

### Bootloader by hand

Hold Esc while plugging in the USB cable. The keyboard starts in the bootloader, where both options can flash
it.

## Going back to stock

Run TEX's original `AP_0407_4.04.exe` the same way. Add `-force` if it says there is nothing to update.

## Known limits

* **Battery percentage** assumes two alkaline AA cells. With NiMH rechargeables it reads low. Fn+B also types the
  raw reading.
* **USB plug and unplug restart the keyboard.** The keyboard's processor sees a power-on reset each
  time, as if its supply dropped for a moment. Settings are kept.
* **No Bluetooth firmware updates.** Updates go over USB through TEX's bootloader.
* **TEX's configurator and macro tool don't work** with this firmware. To remap keys and add shortcuts
  without a compiler, use the [keymap editor](editor/README.md). Otherwise edit `keymap.c` (see [Building](#building)). VIA/Vial live remapping does not fit yet: TEX's bootloader takes
  images up to 28,076 bytes, and v1.0 is 28,072.
* **ISO and JIS boards are untested.** The keymap comes from the stock table, which has the extra ISO key and the
  JIS keys (Ro, Yen, Kana, Henkan, Muhenkan), so they should work. Please report what you find.
* Tested on the Shinobi BLE5 with firmware AP_0407 V1.04.04 only.

## Building

The firmware builds against QMK `qmk_firmware` at the commit in [`qmk_firmware.commit`](qmk_firmware.commit).
With the [QMK CLI](https://docs.qmk.fm/newbs_getting_started) installed (or inside the `ghcr.io/qmk/qmk_cli`
container), from the `shinobi` folder:

    tools/build_firmware.sh ../qmk_firmware default

It clones `qmk_firmware` there if needed, checks out the pinned commit, patches the tree, copies
`qmk/` in as `keyboards/tex/shinobi`, compiles, and checks the image against the bootloader's limits.

`tools/patch_qmk_tree.sh` makes QMK's raw HID reports 64 bytes, which TEX's updater expects. It also fixes the
ChibiOS-Contrib RSTCU base address for this chip. The output, `.build/tex_shinobi_default.bin` in the QMK tree, is linked at
0x3200 behind TEX's bootloader. `tools/build_updater.py AP_0407_4.04.exe <image.bin> <out dir>` wraps an image
into a copy of TEX's updater. The [GitHub Actions workflow](../.github/workflows/build.yml) runs the same script on
every push. Release images are built from a tagged commit and listed with their SHA-256 on the release page.

`tools/tex_selftest.py` runs the stock factory flash self-test over USB (raw HID `14 00`) and prints PASS or FAIL.
The firmware side is only in builds with `TEX_SELFTEST`: add `#define TEX_SELFTEST` to `qmk/config.h` before
building. It costs 84 bytes, more than v1.1 has free, so release images don't answer it.

The other keymaps (`canary`, `canary_slow`, `test90`, `test600`, `diag`, `sleep30`) are developer test
builds from the port. They return to the bootloader on a timer, sleep after 30 s or expose diagnostics. Don't flash them for daily use.

How the port works, the hardware map and the reverse-engineered protocols are in [PORT_NOTES.md](PORT_NOTES.md).

## Credits and license

QMK port by Mauro DiBenedetto. Thanks to TEX for permission to publish, the schematic, and help along the way.
The linker script is adapted from QMK's `annepro2` (MIT; notice in the file).

GPL-2.0-or-later, like QMK. See [LICENSE](../LICENSE). TEX's updater and bootloader are TEX's and are not covered by
this license.
