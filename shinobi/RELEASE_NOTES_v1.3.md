# TEX Shinobi BLE5: QMK v1.3

Fourth release of the open-source QMK firmware for the **TEX Shinobi BLE5**. Fn+Up and Fn+Down now set the
TrackPoint's up/down speed, so the tune is on the arrow keys next to the stick. Play/pause and Stop move to
Fn+PgUp and Fn+PgDn.

**Unofficial.** Not TEX firmware, and not supported by TEX. Published with TEX's permission. TEX's bootloader is
never touched: you can flash the stock firmware back at any time with TEX's own `AP_0407_4.04.exe`.

## Downloads

| File | What it is |
|---|---|
| `tex_flash.exe` | The installer as one Windows file, no Python needed and no administrator rights: `tex_flash.exe tex_shinobi_v1.3.bin`, or an image from the keymap editor. TEX's key is built in, published with TEX's permission. Not signed, so Windows may warn about an unknown publisher (More info, Run anyway). |
| `tex_shinobi_v1.3_updater.exe` | TEX's AP_0407 V1.04.04 updater with this firmware inside in place of the stock image; nothing else in it is changed. Shared with TEX's permission. Run `tex_shinobi_v1.3_updater.exe -force` from a Command Prompt run as administrator. |
| `tex_shinobi_v1.3.bin` | The firmware image, for `tex_flash.exe` or `shinobi/tools/tex_flash.py` (Python 3 and `hidapi`), and the image the [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/) patches. |
| `SHA256SUMS.txt` | SHA-256 of the three files. |

`tex_shinobi_v1.3.bin` is 28,048 bytes, SHA-256 `d9178e744d8ef470b717eb1156d45e0d58c5310403628ce753d15b5f3ee86ab7`.
The keymap editor knows the release by this hash, so the release must carry exactly this image.

Flashing resets the settings (TrackPoint sensitivity, up/down speed, sleep time) to the defaults.

Turn the PC's Bluetooth off before flashing. Full instructions: [shinobi/README.md](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/README.md). Keys, Fn combinations and
known issues: the [owner's manual](https://github.com/cyclistmass/tex-qmk/blob/main/shinobi/MANUAL.md).

## Changed

* **Fn+Down / Fn+Up set the TrackPoint up/down speed** a step slower or faster against left/right, 50 % to 200 %
  in 16 steps, stopping at the ends; Fn+0 makes them the same again. Each press types back `tp3 ud90` and so on.
  Fn - and Fn = still do the same.
* **Play/pause and Stop move to Fn+PgUp and Fn+PgDn** (v1.2 had them on Fn+Down and Fn+Up). Fn+Left and
  Fn+Right are still previous and next track.

Fn+B's line is as in v1.2:

    v1.3 dflt 2026-11-17-17:05:00 bt85% adc3380 aa z15m tp3 ud100 dip24 idl15m34s wk1420ms

## Known limits

As in v1.2.

* **After pulling out the USB cable, switch the keyboard off and on.** Otherwise it doesn't type over Bluetooth,
  although the computer still lists it as connected. TEX's stock firmware does the same, so it comes from the
  hardware or the Bluetooth module, not from this firmware.

In short: battery percentage follows alkaline AA cells (NiMH shows 30-60 % for most of its charge); plugging or
unplugging USB restarts the keyboard; ISO and JIS layouts are untested; DIP switch 6 isn't ported; macros play with
no delays; Fn+B's answers type as on a US layout.

## Tested

On one keyboard (US ANSI, two NiMH AA cells), over USB:

* This release image (`d9178e74...`) flashed with `tex_flash.exe` over the 1.3a test build (2026-11-22), with the
  bootloader's checksum matching and the keyboard back 0.9 s later. Fn+B typed
  `v1.3 dflt 2026-11-17-17:05:00 bt89% adc3443 usb z15m tp3 ud100 dip13 idl1s wk0ms`. Fn+Up typed `tp3 ud105`, and
  Fn+Down stepped back through `ud100`, `ud95` and `ud90`.
* The 1.3a test build, which differs from this image only in the version string and build date (2026-11-17):
  Fn+Down six times and Fn+Up four times typed `ud95` down to `ud60` and back to `ud90`; Fn+PgUp played and paused.

Not tested on this image: Fn+PgUp/PgDn, Bluetooth, flashing over the stock firmware or over v1.2, and the updater exe.
Fn+PgDn sends the media Stop key, which some players (Spotify, browsers) ignore or treat as pause.

Checked off the keyboard (2026-11-17): the image is 28,048 of the 28,076 bytes TEX's bootloader takes, with the
settings record in place; the editor's byte-identity test passes for v1.0 to v1.3. Host tests of the input logic
and the linked signed division pass (`shinobi/test/host/run.sh`, `shinobi/test/host/div_asm.sh`, also in CI).
Built with QMK `f5db962` and arm-none-eabi-gcc 13.2.1, with the build date pinned to `2026-11-17-17:05:00`.
