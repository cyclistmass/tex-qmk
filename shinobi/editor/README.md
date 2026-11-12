# Keymap editor

A static web page that remaps the Shinobi's keys without a compiler. It writes your keymap into the released image
`tex_shinobi_v1.0.bin`, and only into the 960 keymap bytes at 0x3800. It also exports the same keymap as `keymap.c`
for people who build the firmware themselves. Why it works this way is in [DESIGN.md](DESIGN.md).

## Using it

1. Serve this folder and open the page:

       python -I -m http.server 8765 --bind 127.0.0.1

   then open <http://127.0.0.1:8765/index.html>. (Opening `index.html` straight from disk has not been tested.)
2. Load `tex_shinobi_v1.0.bin` from the release page. The page checks its SHA-256 and the default keymap and refuses
   any other image.
3. Pick a layer (Base, Mac, Fn-Ctrl swap, Fn), click a key, and pick what it should do. Tick Ctrl, Shift, Alt or Win
   for a shortcut such as Ctrl+C.
4. **Download firmware** saves `tex_shinobi_v1.0_custom.bin`. Flash it like a release:

       python -I tools/tex_flash.py tex_shinobi_v1.0_custom.bin AP_0407_4.04.exe

   or wrap it into TEX's updater with `tools/build_updater.py`.
5. **Save keymap.json** keeps your keymap so you can load it again later. **Download keymap.c** gives the C source.

Known limits:

* Fn+B still reports the keymap name as `default` in a patched image, because the name is compiled into the code.
* The drawn layout is approximate and has not been checked against the board.
* Sequence macros (several keys in a row, delays) need firmware support that v1.0 doesn't have. See DESIGN.md.

## Files

* `index.html`: the page.
* `editor_core.js`: keycodes, encoding, the image check, patching and export. The page and the tests both use it.
* `shinobi_data.js`: generated facts (layout, default keymap, keycode values, release SHA-256). Regenerate it from
  the pinned QMK tree and the release image:

      python -I ../tools/gen_editor_data.py <qmk_firmware dir> <tex_shinobi_v1.0.bin> shinobi-v1.0 2026-11-04-12:22:53

  The last argument is the release's build date, which Fn+B prints and which a rebuild needs to match the image.

## Testing

`test/byte_identity.sh <tex_shinobi_v1.0.bin> <out dir> <qmk_firmware dir>` is the acceptance test. It needs node,
the QMK CLI and the ARM toolchain (in WSL on Windows). It:

* checks the editor core: keycode round trips, and that a changed code byte, a changed keymap byte, a short image and
  a changed bootloader record are all refused;
* compiles the editor's export of the default keymap with the release's build date, which must equal the release;
* changes a key on every layer and adds shortcuts, then checks that the patched release equals a compiled build of
  the exported `keymap.c`.

`test/qmk_fixed_date.sh` and `test/build_wsl.sh` are its helpers: QMK stamps the build date into the image, so the
test pins it.
