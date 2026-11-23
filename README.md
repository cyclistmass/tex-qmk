# QMK firmware for TEX keyboards

Unofficial open-source [QMK](https://qmk.fm) firmware for the TEX Shinobi BLE5, with USB, Bluetooth, TrackPoint and battery sleep.

**Unofficial.** This is not TEX firmware, and TEX does not support it. It is published with TEX's permission.
TEX's bootloader is never touched, so the stock firmware can always be flashed back.

## Download for the TEX Shinobi BLE5

Download the [firmware: `tex_shinobi_v1.4.bin`](https://github.com/cyclistmass/tex-qmk/releases/download/shinobi-v1.4/tex_shinobi_v1.4.bin) and one installer:

| Your computer | Download installer |
|---|---|
| Windows | [`tex_flash.exe`](https://github.com/cyclistmass/tex-qmk/releases/latest/download/tex_flash.exe) |
| Mac with Apple silicon (M1 and later) | [`tex_flash_macos_arm64`](https://github.com/cyclistmass/tex-qmk/releases/latest/download/tex_flash_macos_arm64) |
| Mac with an Intel processor | [`tex_flash_macos_x86_64`](https://github.com/cyclistmass/tex-qmk/releases/latest/download/tex_flash_macos_x86_64) |

**Not yet tested with a keyboard on a Mac:** it builds and starts on Apple's Intel and Apple-silicon machines, finds no keyboard there, and stops as it should. Please report what happens on yours.

**New in v1.4:** switching between your three Bluetooth computers works like the stock firmware, Fn+M switches
the Mac layout, and flashing keeps your settings. [Release notes](shinobi/RELEASE_NOTES_v1.4.md).

## Install in three steps

1. Download the firmware and the installer for your computer to the same folder.
2. Plug the keyboard in with the USB cable and turn the computer's Bluetooth off.
3. Run the installer on the firmware. Follow the [Windows or Mac commands and success check](shinobi/README.md#installing).

The [Shinobi README](shinobi/README.md) also covers other operating systems, TEX's updater, and going back to stock.
The [owner's manual](shinobi/MANUAL.md) covers every key and light, Bluetooth, sleep, troubleshooting and known issues.

## Keyboards

Each folder has its own README with what works, how to install it, and how to go back to the stock firmware.

| Keyboard | Folder | Status |
|---|---|---|
| TEX Shinobi BLE5 | [`shinobi/`](shinobi/) ([manual](shinobi/MANUAL.md), [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/)) | v1.4: USB, Bluetooth with three hosts, TrackPoint, battery sleep, keymap editor |

Downloads are on the [Releases](https://github.com/cyclistmass/tex-qmk/releases) page. The documentation is also
published as a website at <https://cyclistmass.github.io/tex-qmk/>, rebuilt from this repository on every push.

## Layout

Each keyboard folder holds:

* `README.md`: for owners. Installing, Fn keys, known limits.
* `MANUAL.md`: the owner's manual. Every key and light, Bluetooth, sleep, troubleshooting, known issues.
* `PORT_NOTES.md`: how the port works, the hardware map, and the reverse-engineered protocols.
* `qmk/`: the QMK keyboard source, copied into a QMK tree as `keyboards/tex/<keyboard>`.
* `tools/`: the build, flashing and updater scripts for that keyboard.
* `editor/`: a web page that remaps keys in a release image, with its tests.
* `qmk_firmware.commit`: the QMK commit it builds against.

## License

GPL-2.0-or-later, like QMK. See [LICENSE](LICENSE). TEX's updaters and bootloaders are TEX's and are not covered
by this license.
