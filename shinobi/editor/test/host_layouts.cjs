// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
// Host keyboard layout checks for the editor core: macro text to HID usages per layout, back again, key labels and
// keymap.json. Needs no release image. usage: node host_layouts.cjs
"use strict";
require("../shinobi_data.js");
const { makeCore, layouts } = require("../editor_core.js");

const t0 = Date.now();
let failures = 0;
function check(cond, what) {
    console.log(`${cond ? "PASS" : "FAIL"} ${what}`);
    if (!cond) failures++;
}
const hex = (b) => b.map((x) => x.toString(16).toUpperCase().padStart(2, "0")).join(" ");
const D = globalThis.SHINOBI_DATA;
const tag = D.releases.find((r) => r.macros).tag;
const cores = Object.fromEntries(layouts.map((id) => [id, makeCore(D, tag, { hostLayout: id })]));
const layoutName = { us: "US", uk: "UK", de: "German", fr: "French", es: "Spanish", nordic: "Nordic (Swedish, Finnish)", jis: "Japanese (JIS)" };

// Every character a layout can type round-trips: text -> usages -> text -> the same usages.
for (const id of layouts) {
    const c = cores[id];
    const chars = [];
    for (let cp = 0x20; cp < 0x250; cp++) {
        try { c.parseMacro(String.fromCodePoint(cp)); chars.push(String.fromCodePoint(cp)); } catch (e) { /* not on this layout */ }
    }
    const text = chars.join("").replace(/\{/g, "{{") + "{Ctrl+Z}{Ctrl+A}{Win+R}{Enter}";
    const b = c.parseMacro(text);
    const back = c.formatMacro(b);
    check(hex(c.parseMacro(back)) === hex(b), `${id}: all ${chars.length} typable characters round-trip`);
    check(chars.length >= 94, `${id}: types at least the 94 printable ASCII characters' worth (${chars.length})`);
}

// Known encodings, from the Windows layouts (AltGr is E6, Shift E1, a dead key is followed by Space 2C or a letter).
const cases = [
    ["us", "He", "E1 0B 08"], ["us", "{{", "E1 2F"], ["us", "~", "E1 35"], ["us", "{Ctrl+Z}", "E0 1D"],
    ["uk", "@", "E1 34"], ["uk", "\"", "E1 1F"], ["uk", "#", "31"], ["uk", "\\", "64"], ["uk", "€", "E6 21"], ["uk", "Á", "E1 E6 04"],
    ["de", "z", "1C"], ["de", "Y", "E1 1D"], ["de", "@", "E6 14"], ["de", "^", "35 2C"], ["de", "é", "2E 08"],
    ["de", "É", "2E E1 08"], ["de", "{{", "E6 24"], ["de", "{Ctrl+Z}", "E0 1C"], ["de", "ß", "2D"], ["de", "|", "E6 64"],
    ["fr", "a", "14"], ["fr", "1", "E1 1E"], ["fr", "m", "33"], ["fr", "{{", "E6 21"], ["fr", "ê", "2F 08"], ["fr", "^", "E6 26"],
    ["fr", "~", "E6 1F 2C"], ["fr", ",", "10"], ["fr", "{Ctrl+A}", "E0 14"], ["fr", "{Ctrl+1}", "E0 1E"],
    ["es", "ñ", "33"], ["es", "á", "34 04"], ["es", "~", "E6 21 2C"], ["es", "@", "E6 1F"], ["es", "¿", "E1 2E"],
    ["nordic", "å", "2F"], ["nordic", "~", "E6 30 2C"], ["nordic", "ü", "30 18"], ["nordic", "$", "E6 21"],
    ["jis", "@", "2F"], ["jis", "_", "E1 87"], ["jis", "\"", "E1 1F"], ["jis", "~", "E1 2E"], ["jis", ":", "34"], ["jis", "\\", "87"],
];
for (const [id, text, want] of cases) {
    let got;
    try { got = hex(cores[id].parseMacro(text)); } catch (e) { got = e.message; }
    check(got === want, `${id}: ${JSON.stringify(text)} is ${want} (${got})`);
}
for (const [id, text] of [["us", "é"], ["fr", "ß"], ["fr", "É"], ["jis", "é"], ["uk", "ä"], ["de", "ñ"]]) {
    let msg = "";
    try { cores[id].parseMacro(text); } catch (e) { msg = e.message; }
    const name = layoutName[id];
    check(msg.includes("can't type") && msg.includes(name), `${id}: ${JSON.stringify(text)} refused, naming the layout (${msg})`);
}
check(cores.de.formatMacro([0x35, 0x2c, 0x2e, 0x08, 0x1c]) === "^éz", `de: 35 2C 2E 08 1C reads back as "^éz" (${cores.de.formatMacro([0x35, 0x2c, 0x2e, 0x08, 0x1c])})`);
check(cores.de.formatMacro([0x35]) === "{GRV}", `de: a dead key alone reads back as a key (${cores.de.formatMacro([0x35])})`);
check(cores.de.formatMacro([0xe6, 0xe1, 0x04]) === "{RAlt+Shift+A}", `de: modifiers in another order stay keys (${cores.de.formatMacro([0xe6, 0xe1, 0x04])})`);

// Labels show what the host types.
const r = (c, t) => c.label(c.resolve(t));
for (const [id, tok, want] of [["us", "KC_A", "A"], ["us", "KC_GRV", "`"], ["us", "KC_1", "1"], ["us", "KC_NUBS", "ISO \\"],
    ["de", "KC_Y", "Z"], ["de", "KC_Z", "Y"], ["de", "KC_SCLN", "Ö"], ["de", "KC_GRV", "^"], ["de", "LCTL(KC_Y)", "Ctrl+Z"],
    ["fr", "KC_1", "1 &"], ["fr", "KC_Q", "A"], ["fr", "KC_M", ","], ["jis", "KC_INT3", "¥"], ["jis", "KC_GRV", "`"],
    ["uk", "KC_NUHS", "#"], ["es", "KC_SCLN", "Ñ"]]) {
    check(r(cores[id], tok) === want, `${id}: ${tok} is labelled ${want} (${r(cores[id], tok)})`);
}
check(/types z, Shift Z on a German layout/.test(cores.de.title(cores.de.resolve("KC_Y"))), `de: KC_Y's title says what it types (${cores.de.title(cores.de.resolve("KC_Y"))})`);

// keymap.json keeps the layout, and a file is read with its own layout whatever the page has chosen.
const de = cores.de;
const L = de.defaultLayers();
const macros = ["Grüße{Enter}", "{Ctrl+Z}"];
const json = de.toJSON(L, macros);
check(JSON.parse(json).host_layout === "de", "keymap.json records host_layout");
const back = cores.us.fromJSON(json);
check(back.hostLayout === "de" && back.macros[0] === macros[0], `a German keymap.json loads as German from a US page (${back.hostLayout})`);
const old = JSON.parse(json); delete old.host_layout; old.macros = ["Hi"];
check(cores.de.fromJSON(JSON.stringify(old)).hostLayout === "us", "a keymap.json without host_layout is US");
old.host_layout = "xx";
let bad = ""; try { cores.us.fromJSON(JSON.stringify(old)); } catch (e) { bad = e.message; }
check(/unknown keyboard layout/.test(bad), `an unknown layout is refused (${bad})`);
check(hex(Array.from(de.encodeMacros(macros).table.subarray(0, 4))) === "E1 0A 15 2F", "a German macro is encoded with German keys");

const t1 = Date.now();
console.log(`TIMING label=host_layouts start=${Math.floor(t0 / 1000)} end=${Math.floor(t1 / 1000)} seconds=${((t1 - t0) / 1000).toFixed(1)} result=${failures ? "fail" : "ok"}`);
process.exit(failures ? 1 : 0);
