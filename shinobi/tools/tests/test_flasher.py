# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Hardware-free tests of the flasher: argument parsing, image checks, the message table, locale selection,
device selection (with a fake hidapi) and the dry-run comparison.

    python -I -m pytest shinobi/tools/tests
    python -I shinobi/tools/tests/test_flasher.py      # plain asserts, no pytest needed

Nothing here opens a HID device or flashes anything.
"""
import json
import os
import re
import string
import struct
import sys
import types

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import build_updater as bu  # noqa: E402
import tex_flash  # noqa: E402
import tex_i18n  # noqa: E402
import tex_iap_probe as probe  # noqa: E402
import tex_key  # noqa: E402


def fields(template):
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def raises_exit(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except SystemExit as e:
        return str(e.code)
    raise AssertionError("expected SystemExit")


def good_image(size=0xC00):
    img = bytearray(b"\xff" * size)
    struct.pack_into("<II", img, 0, 0x20004000, 0x3201)
    img[bu.RECORD_AT:bu.RECORD_AT + len(bu.RECORD)] = bu.RECORD
    return bytes(img)


# ---- message table ----------------------------------------------------------------------------------------

def test_every_message_has_every_language():
    for key, msgs in tex_i18n.MESSAGES.items():
        assert set(msgs) == set(tex_i18n.LANGS), key
        for lang, text in msgs.items():
            assert text.strip(), (key, lang)


def test_placeholders_match_english():
    for key, msgs in tex_i18n.MESSAGES.items():
        want = fields(msgs["en"])
        for lang, text in msgs.items():
            assert fields(text) == want, (key, lang)
            text.format(**{f: "x" for f in want})


def test_used_keys_exist_and_table_has_no_dead_keys():
    used = set()
    for name in os.listdir(TOOLS):
        if name.endswith(".py"):
            src = open(os.path.join(TOOLS, name), encoding="utf-8").read()
            used |= set(re.findall(r'\bt\(\s*"(\w+)"', src))
    assert used <= set(tex_i18n.MESSAGES), used - set(tex_i18n.MESSAGES)
    assert set(tex_i18n.MESSAGES) <= used, set(tex_i18n.MESSAGES) - used


def test_translations_differ_from_english_where_expected():
    # catches a table row left as a copy of the English text (lang_fallback is English by design)
    for key, msgs in tex_i18n.MESSAGES.items():
        if key == "lang_fallback":
            continue
        for lang in tex_i18n.LANGS[1:]:
            assert msgs[lang] != msgs["en"], (key, lang)


# ---- locale selection -------------------------------------------------------------------------------------

def test_normalize():
    n = tex_i18n.normalize
    assert n("ja_JP.UTF-8") == "ja"
    assert n("de_DE@euro") == "de"
    assert n("fr-CA") == "fr"
    assert n("es_MX.utf8") == "es"
    assert n("en_US") == "en"
    assert n("zh_TW.UTF-8") == "zh-TW" and n("zh-Hant") == "zh-TW" and n("zh_HK") == "zh-TW" and n("zh") == "zh-TW"
    assert n("zh_CN.UTF-8") is None and n("zh-Hans") is None
    assert n("pt_BR") is None and n("C") is None and n("") is None and n(None) is None


def test_environment_order():
    f = tex_i18n.from_environment
    assert f({"LC_ALL": "de_DE.UTF-8", "LANG": "fr_FR.UTF-8"}) == "de"
    assert f({"LC_MESSAGES": "es_ES.UTF-8", "LANG": "fr_FR.UTF-8"}) == "es"
    assert f({"LANG": "ja_JP.UTF-8"}) == "ja"
    assert f({"LANG": "en_US.UTF-8", "LANGUAGE": "fr:de"}) == "fr"  # LANGUAGE is a preference list
    assert f({"LANG": "de_DE.UTF-8", "LANGUAGE": "pt:xx"}) == "de"  # nothing usable in it: the locale
    assert f({"LC_ALL": "C", "LANGUAGE": "fr"}) == "en"  # the C locale ignores LANGUAGE
    assert f({"LANG": "POSIX"}) == "en"
    assert f({"LANG": "pt_BR.UTF-8"}, windows_ui="") is None  # unsupported: the caller falls back to English
    assert f({}, windows_ui="") is None


def test_windows_ui_language_used_when_environment_is_empty():
    f = tex_i18n.from_environment
    assert f({}, windows_ui="ja") == "ja"
    assert f({}, windows_ui="zh_TW") == "zh-TW"
    assert f({}, windows_ui="zh_CN") is None
    assert f({"LANG": "de_DE.UTF-8"}, windows_ui="ja") == "de"  # the environment wins (Git Bash, MSYS)


def test_pick_override_and_fallback():
    assert tex_i18n.pick("fr", environ={"LANG": "de_DE"})[0] == "fr"  # --lang beats the locale
    assert tex_i18n.pick(None, environ={"LANG": "de_DE"})[0] == "de"
    assert tex_i18n.pick(None, environ={"LANG": "pt_BR"}, windows_ui="")[0] == "en"
    assert tex_i18n.pick(None, environ={}, windows_ui="")[0] == "en"
    lang, note = tex_i18n.pick("ja", encoding="cp1252")  # a cp1252 pipe cannot show Japanese
    assert lang == "en" and "cp1252" in note and "ja" in note
    assert tex_i18n.pick("ja", encoding="utf-8") == ("ja", None)
    assert tex_i18n.pick("de", encoding="cp1252") == ("de", None)  # German fits cp1252
    assert tex_i18n.encodable("fr", "ascii") is False and tex_i18n.encodable("en", "ascii") is True


def test_set_language_and_t():
    tex_i18n.set_language("de")
    try:
        assert tex_i18n.t("erasing") == "Löschen und Schreiben"
        assert tex_i18n.t("erasing", in_lang="en") == "erasing and writing"
    finally:
        tex_i18n.set_language("en")


# ---- arguments --------------------------------------------------------------------------------------------

def test_parse_args():
    a = tex_flash.parse_args(["fw.bin", "key.bin"])
    assert (a.image, a.key, a.wait, a.dry_run, a.lang) == ("fw.bin", "key.bin", 15, None, None)
    a = tex_flash.parse_args(["fw.bin", "AP_0407_4.04.exe", "--wait", "3", "--lang", "zh_TW", "--dry-run", "t.jsonl"])
    assert (a.wait, a.lang, a.dry_run) == (3.0, "zh-TW", "t.jsonl")
    assert tex_i18n.current() in ("zh-TW", "en")  # English when a piped cp1252 stdout cannot show Chinese
    tex_i18n.set_language("en")


def test_parse_args_rejects_bad_input():
    for bad in ([], ["only.bin"], ["a", "b", "--lang", "xx"], ["a", "b", "--wait", "soon"], ["a", "b", "--zap"]):
        try:
            tex_flash.parse_args(bad)
        except SystemExit as e:
            assert e.code == 2, bad
        else:
            raise AssertionError(bad)
    tex_i18n.set_language("en")


# ---- image and key checks ---------------------------------------------------------------------------------

def test_good_image_passes():
    assert bu.check_image(good_image()) == (0x20004000, 0x3201)


def test_bad_images_are_refused_with_a_message():
    tex_i18n.set_language("en")
    assert "28076" in raises_exit(bu.check_image, b"\x00" * (bu.SLOT + 1))
    assert "0 bytes" in raises_exit(bu.check_image, b"")
    img = bytearray(good_image())
    struct.pack_into("<I", img, 0, 0x10000000)
    assert "not in SRAM" in raises_exit(bu.check_image, bytes(img))
    img = bytearray(good_image())
    struct.pack_into("<I", img, 4, 0x3200)  # even: not Thumb
    assert "Thumb" in raises_exit(bu.check_image, bytes(img))
    img = bytearray(good_image())
    img[bu.RECORD_AT] ^= 1
    assert "0x3bf8" in raises_exit(bu.check_image, bytes(img))


def test_image_messages_in_every_language():
    for lang in tex_i18n.LANGS:
        tex_i18n.set_language(lang)
        try:
            msg = raises_exit(bu.check_image, b"\x00" * (bu.SLOT + 1))
        finally:
            tex_i18n.set_language("en")
        assert msg == tex_i18n.t("image_size", in_lang=lang, n=bu.SLOT + 1, max=bu.SLOT)


def test_key_load_failures():
    import tempfile
    d = tempfile.mkdtemp()
    missing = os.path.join(d, "nope.bin")
    assert "cannot read" in raises_exit(tex_key.load, missing)
    wrong = os.path.join(d, "wrong.bin")
    open(wrong, "wb").write(b"\x00" * 52)
    assert "not the TEX Shinobi key" in raises_exit(tex_key.load, wrong)
    other = os.path.join(d, "other.exe")
    open(other, "wb").write(b"MZ" + b"\x00" * 100)  # read as data, never run
    assert "AP_0407_4.04.exe" in raises_exit(tex_key.load, other)


# ---- reports and the dry run ------------------------------------------------------------------------------

def test_plan_shape():
    enc = bytes(range(256)) * 4
    vb = b"\x1a\x00" + bytes(174) + b"\xa5\x5a" + b"\x00\x00"
    assert tex_flash.valid_version_block(vb)
    steps = tex_flash.plan(enc, vb)
    assert steps[0][0] == "erase" and steps[-1][0] == "start" and steps[-1][1] == [0x11, 0x01]
    assert steps[0][1][:2] == [0x1D, 0x00]
    blocks = [s for s in steps if s[0] == "block"]
    assert len(blocks) == -(-len(enc) // 52) + -(-len(vb) // 52)
    assert all(len(p) <= 4 + 52 for _, p, _ in steps)
    assert tex_flash.word_sum(enc) == sum(struct.unpack("<%dI" % (len(enc) // 4), enc)) & 0xFFFFFFFF


def transcript_for(steps):
    return [{"dir": "write", "hex": tex_flash.padded(p).hex()} for _, p, _ in steps]


def test_dry_run_matches_and_detects_a_difference():
    enc = bytes(range(256)) * 4
    vb = b"\x1a\x00" + bytes(174) + b"\xa5\x5a" + b"\x00\x00"
    steps = tex_flash.plan(enc, vb)
    rows = [{"dir": "write", "hex": "1200" + "00" * 62}] + transcript_for(steps)  # an info read first is ignored
    assert tex_flash.dry_run(steps, rows) is None
    bad = [dict(r) for r in rows]
    bad[5]["hex"] = "ff" + bad[5]["hex"][2:]
    assert "differs" in raises_exit(tex_flash.dry_run, steps, bad)


def test_transcript_reading():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "t.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"dir": "write", "hex": "00"}) + "\n\n" + json.dumps({"dir": "read", "hex": "11"}) + "\n")
    assert [r["dir"] for r in tex_flash.read_transcript(p)] == ["write", "read"]
    assert "cannot read" in raises_exit(tex_flash.read_transcript, p + ".missing")


# ---- device selection, with a fake hidapi -----------------------------------------------------------------

class FakeHid:
    def __init__(self, devices):
        self.devices = devices

    def enumerate(self, vid=0):
        return [d for d in self.devices if not vid or d["vendor_id"] == vid]

    def device(self):
        raise AssertionError("tests never open a device")


def dev(pid, page, path, vid=0x04D9, iface=0):
    return {"vendor_id": vid, "product_id": pid, "usage_page": page, "usage": 1, "path": path,
            "interface_number": iface, "product_string": "x"}


def with_fake(devices, fn):
    old = probe.hid_module
    probe.hid_module = lambda: FakeHid(devices)
    try:
        return fn()
    finally:
        probe.hid_module = old


def test_vendor_interface_is_found_by_vid_and_usage_page_not_by_path():
    # the same keyboard as each OS names it: Windows, Linux hidraw, FreeBSD, OpenBSD
    for paths in ((b"\\\\?\\HID#VID_04D9&PID_0407&MI_02#7&abc", b"\\\\?\\HID#VID_04D9&PID_0407&MI_00#7&def"),
                  (b"/dev/hidraw4", b"/dev/hidraw3"),
                  (b"/dev/uhid2", b"/dev/uhid1"),
                  (b"/dev/uhid1", b"/dev/uhid0")):
        devices = [dev(0x0407, 0x0001, paths[1]), dev(0x0407, 0xFF00, paths[0], iface=2),
                   dev(0x046D, 0xFF00, b"/dev/other", vid=0x046D)]
        assert with_fake(devices, lambda: probe.vendor_path(probe.APP)) == paths[0]
        assert with_fake(devices, probe.modes) == [probe.APP]


def test_single_interface_fallback_and_ambiguity():
    one = [dev(0x1407, 0x0000, b"/dev/hidraw9")]
    assert with_fake(one, lambda: probe.vendor_path(probe.IAP)) == b"/dev/hidraw9"
    two = [dev(0x1407, 0x0001, b"/a"), dev(0x1407, 0x0002, b"/b")]
    assert with_fake(two, lambda: probe.vendor_path(probe.IAP)) is None  # no guess between two non-vendor ones
    assert with_fake([], lambda: probe.describe(probe.modes())) == tex_i18n.t("modes_none")


def test_hidapi_is_not_imported_until_needed():
    saved = sys.modules.get("hid")
    sys.modules["hid"] = None  # makes `import hid` raise ImportError
    try:
        msg = raises_exit(probe.hid_module)
    finally:
        if saved is None:
            sys.modules.pop("hid", None)
        else:
            sys.modules["hid"] = saved
    assert "hidapi" in msg


def test_open_failure_points_at_the_permission_docs():
    class Refusing:
        def device(self):
            return types.SimpleNamespace(open_path=lambda p: (_ for _ in ()).throw(OSError("open failed")))

    old = probe.hid_module
    probe.hid_module = lambda: Refusing()
    try:
        msg = raises_exit(probe.open_device, b"/dev/hidraw0")
    finally:
        probe.hid_module = old
    assert "open failed" in msg and ("unix/README.md" in msg or sys.platform == "win32")


def test_udev_rule_covers_both_modes():
    lines = open(os.path.join(TOOLS, "unix", "70-tex-shinobi.rules"), encoding="utf-8").read().lower().splitlines()
    rule = " ".join(ln for ln in lines if not ln.lstrip().startswith("#"))
    assert "04d9" in rule and "0407" in rule and "1407" in rule and "uaccess" in rule
    assert "mode=\"0666\"" not in rule and "setuid" not in rule


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print("FAIL", name, type(e).__name__, e)
    print("failed:", failed)
    sys.exit(1 if failed else 0)
