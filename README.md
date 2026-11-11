# QMK firmware for TEX keyboards

Unofficial open-source [QMK](https://qmk.fm) firmware for TEX keyboards, one folder per keyboard. Each folder
has its own README with what works, how to install it, and how to go back to the stock firmware.

| Keyboard | Folder | Status |
|---|---|---|
| TEX Shinobi BLE5 | [`shinobi/`](shinobi/) | v1.0: USB, Bluetooth with three hosts, TrackPoint, battery sleep |

**Unofficial.** This is not TEX firmware, and TEX does not support it. It is published with TEX's permission.
TEX's bootloader is never touched, so the stock firmware can always be flashed back.

Downloads are on the [Releases](https://github.com/cyclistmass/tex-qmk/releases) page.

## Layout

Each keyboard folder holds:

* `README.md`: for owners. Installing, Fn keys, known limits.
* `PORT_NOTES.md`: how the port works, the hardware map, and the reverse-engineered protocols.
* `qmk/`: the QMK keyboard source, copied into a QMK tree as `keyboards/tex/<keyboard>`.
* `tools/`: the build, flashing and updater scripts for that keyboard.
* `qmk_firmware.commit`: the QMK commit it builds against.

## License

GPL-2.0-or-later, like QMK. See [LICENSE](LICENSE). TEX's updaters and bootloaders are TEX's and are not covered
by this license.
