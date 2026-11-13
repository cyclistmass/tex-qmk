// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
// Translation table checks: every language has every English string with the same {placeholders} and, for HTML
// strings, the same tags; the language pick from the browser; and the core in each language still reads macros
// with English key names. Needs no release image. usage: node i18n.cjs
"use strict";
require("../shinobi_data.js");
const { tables, pick, languages, translator } = require("../i18n.js");
const { makeCore } = require("../editor_core.js");

const t0 = Date.now();
let failures = 0;
function check(cond, what) {
    console.log(`${cond ? "PASS" : "FAIL"} ${what}`);
    if (!cond) failures++;
}
const D = globalThis.SHINOBI_DATA;
const en = tables.en;
const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(" ");
const tags = (s) => (s.match(/<[^>]+>/g) || []).sort().join(" ");
const layerIds = new Set(D.layers.map((l) => l.id));
const optional = (k) => /^key\.[A-Z_0-9]+$/.test(k) || (/^layer\./.test(k) && layerIds.has(k.slice(6)));

check(languages.map((l) => l.id).join(" ") === Object.keys(tables).join(" "), `menu lists every table (${languages.map((l) => l.id).join(", ")})`);
for (const { id } of languages) {
    if (id === "en") continue;
    const tb = tables[id];
    const missing = Object.keys(en).filter((k) => !(k in tb));
    const extra = Object.keys(tb).filter((k) => !(k in en) && !optional(k));
    check(!missing.length && !extra.length, `${id}: has every string (${missing.length} missing ${missing.slice(0, 3)}, ${extra.length} unknown ${extra.slice(0, 3)})`);
    const badHoles = Object.keys(en).filter((k) => k in tb && holes(tb[k]) !== holes(en[k]));
    check(!badHoles.length, `${id}: same {placeholders} as English (${badHoles.slice(0, 3).map((k) => `${k}: ${holes(tb[k])}`)})`);
    const badTags = Object.keys(en).filter((k) => /_html$/.test(k) && tags(tb[k]) !== tags(en[k]));
    check(!badTags.length, `${id}: HTML strings keep English's tags (${badTags})`);
    const same = Object.keys(en).filter((k) => en[k] && tb[k] === en[k]);
    check(same.length < 25, `${id}: ${same.length} strings identical to English (codes and names such as ${same.slice(0, 4).join(", ")})`);
    check(!!tb["ui.machine"], `${id}: says the translation is machine-made`);
}
check(en["ui.machine"] === "", "English has no machine-translation note");

for (const [langs, want] of [[["de-AT", "en"], "de"], [["zh-TW"], "zh-Hant"], [["zh-Hant-HK"], "zh-Hant"], [["zh-CN", "ja-JP"], "ja"],
    [["zh-CN"], "en"], [["pt-BR", "fr-CA"], "fr"], [["es-419"], "es"], [[], "en"], [undefined, "en"]]) {
    check(pick(langs) === want, `browser ${JSON.stringify(langs)} picks ${want} (${pick(langs)})`);
}
const t = translator("xx");
check(t.lang === "en" && t("ui.dlc") === en["ui.dlc"], "an unknown language falls back to English");
check(translator("de")("ui.meter", { used: 3, size: 96 }) === "3 von 96 Bytes", "placeholders are filled");
check(translator("en")("err.cantType", { ch: "\"é\"", layout: "US" }).includes("{Name}"), "macro syntax such as {Name} is left alone");

// The core in every language: messages translated, macro key names English.
const tag = D.releases.find((r) => r.macros).tag;
for (const { id } of languages) {
    const c = makeCore(D, tag, { lang: id, hostLayout: "de" });
    let msg = "";
    try { c.parseMacro("ñ"); } catch (e) { msg = e.message; }
    check(msg === translator(id)("err.cantType", { ch: "\"ñ\"", layout: translator(id)("layout.de") }), `${id}: can't-type message in ${id}: ${msg}`);
    check(c.parseMacro("{Enter}{Bksp}{Ctrl+Z}{Esc}").join(" ") === "40 42 224 28 41", `${id}: {Enter}{Bksp}{Ctrl+Z}{Esc} parse with English names`);
    check(c.formatMacro(c.parseMacro("a{Enter}{Win+R}")) === "a{Enter}{Win+R}", `${id}: macros read back with English key names`);
    check(c.catalog.every((g) => g.group && !/^grp\./.test(g.group)), `${id}: catalog groups are named (${c.catalog[0].group}, ${c.catalog[12].group})`);
    check(c.label(c.resolve("MS_BTN1")) === (id === "en" ? "Left click" : tables[id]["key.MS_BTN1"]), `${id}: MS_BTN1 reads ${c.label(c.resolve("MS_BTN1"))}`);
    check(/^\S/.test(c.label(c.resolve("MO(_FN)"))), `${id}: MO(_FN) reads ${c.label(c.resolve("MO(_FN)"))}`);
}
const t1 = Date.now();
console.log(`TIMING label=i18n start=${Math.floor(t0 / 1000)} end=${Math.floor(t1 / 1000)} seconds=${((t1 - t0) / 1000).toFixed(1)} result=${failures ? "fail" : "ok"}`);
process.exit(failures ? 1 : 0);
