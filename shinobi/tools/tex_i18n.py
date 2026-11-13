# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""User-facing messages of the TEX Shinobi flasher, in six languages, and the choice of language.

Languages: en, zh-TW (Traditional Chinese), ja, de, fr, es. English is the reference and the fallback. The other
five are machine-assisted and NOT reviewed by native speakers; fixes are welcome.

Every message the flasher prints for a person goes through t(key, **values) and is defined once in MESSAGES.
Lines meant for bug reports (hex dumps, report and pointer mismatches, the image summary line, OS error texts
inside {detail}/{err}) are not in the table and stay in English on purpose.

The language is chosen by pick(): the --lang value if given, else the locale (LC_ALL, LC_MESSAGES, LANG, with
LANGUAGE as a list of preferences; on Windows also the user's UI language), else English. A language is skipped
when the output encoding cannot show its text (a cp1252 pipe cannot show Japanese).
"""
import os
import sys

LANGS = ("en", "zh-TW", "ja", "de", "fr", "es")
DEFAULT = "en"

MESSAGES = {
    "help_desc": {
        "en": "Flash the TEX Shinobi through its stock bootloader (IAP), without the vendor updater.",
        "zh-TW": "透過原廠啟動載入器 (IAP) 燒錄 TEX Shinobi,不需要廠商的更新程式。",
        "ja": "メーカーのアップデータを使わず、純正ブートローダー (IAP) 経由で TEX Shinobi に書き込みます。",
        "de": "Flasht das TEX Shinobi über seinen Original-Bootloader (IAP), ohne das Updater-Programm des Herstellers.",
        "fr": "Flashe le TEX Shinobi via son bootloader d'origine (IAP), sans l'outil de mise à jour du fabricant.",
        "es": "Graba el TEX Shinobi con su bootloader original (IAP), sin el actualizador del fabricante.",
    },
    "help_image": {
        "en": "firmware image linked at 0x3200 (a .bin)",
        "zh-TW": "連結於 0x3200 的韌體映像檔 (.bin)",
        "ja": "0x3200 にリンクされたファームウェアイメージ (.bin)",
        "de": "Firmware-Image, gelinkt auf 0x3200 (.bin)",
        "fr": "image du firmware liée à 0x3200 (.bin)",
        "es": "imagen de firmware enlazada en 0x3200 (.bin)",
    },
    "help_key": {
        "en": "TEX's own AP_0407_4.04.exe (read as data, never run) or the 52-byte key file",
        "zh-TW": "TEX 的 AP_0407_4.04.exe(只當資料讀取,不會執行)或 52 位元組的金鑰檔",
        "ja": "TEX 純正の AP_0407_4.04.exe(データとして読むだけで実行しません)または 52 バイトの鍵ファイル",
        "de": "TEXs eigene AP_0407_4.04.exe (wird nur als Daten gelesen, nie ausgeführt) oder die 52-Byte-Schlüsseldatei",
        "fr": "l'AP_0407_4.04.exe de TEX (lu comme données, jamais exécuté) ou le fichier de clé de 52 octets",
        "es": "el AP_0407_4.04.exe de TEX (se lee como datos, nunca se ejecuta) o el archivo de clave de 52 bytes",
    },
    "help_wait": {
        "en": "seconds to watch USB after the restart (default 15)",
        "zh-TW": "重新啟動後監看 USB 的秒數(預設 15)",
        "ja": "再起動後に USB を監視する秒数(既定 15)",
        "de": "Sekunden, die USB nach dem Neustart beobachtet wird (Standard 15)",
        "fr": "secondes de surveillance de l'USB après le redémarrage (15 par défaut)",
        "es": "segundos que se vigila el USB tras el reinicio (15 por defecto)",
    },
    "help_dry": {
        "en": "build the reports and compare them with a recorded vendor transcript; the keyboard is not opened",
        "zh-TW": "產生報告並與錄下的廠商紀錄比對;不會開啟鍵盤",
        "ja": "レポートを作成し、記録済みのメーカーのトランスクリプトと比較します。キーボードは開きません",
        "de": "Reports erzeugen und mit einem aufgezeichneten Hersteller-Transkript vergleichen; die Tastatur wird nicht geöffnet",
        "fr": "construit les rapports et les compare à une trace du fabricant enregistrée ; le clavier n'est pas ouvert",
        "es": "genera los informes y los compara con una traza grabada del fabricante; no se abre el teclado",
    },
    "help_lang": {
        "en": "message language: en, zh-TW, ja, de, fr, es (default: from the system locale, else en)",
        "zh-TW": "訊息語言:en、zh-TW、ja、de、fr、es(預設:依系統語系,否則 en)",
        "ja": "メッセージの言語: en, zh-TW, ja, de, fr, es(既定: システムのロケール、なければ en)",
        "de": "Sprache der Meldungen: en, zh-TW, ja, de, fr, es (Standard: Systemsprache, sonst en)",
        "fr": "langue des messages : en, zh-TW, ja, de, fr, es (par défaut : locale du système, sinon en)",
        "es": "idioma de los mensajes: en, zh-TW, ja, de, fr, es (por defecto: configuración regional, si no en)",
    },
    "lang_fallback": {  # always shown in English: the chosen language could not be shown
        "en": "output encoding {enc} cannot show {lang}; using English",
        "zh-TW": "output encoding {enc} cannot show {lang}; using English",
        "ja": "output encoding {enc} cannot show {lang}; using English",
        "de": "output encoding {enc} cannot show {lang}; using English",
        "fr": "output encoding {enc} cannot show {lang}; using English",
        "es": "output encoding {enc} cannot show {lang}; using English",
    },
    "dry_ok": {
        "en": "dry run: all {n} reports from erase to start match the vendor transcript byte for byte",
        "zh-TW": "模擬執行:從抹除到啟動的 {n} 個報告與廠商紀錄逐位元組完全相符",
        "ja": "ドライラン: 消去から起動までの {n} 件のレポートがメーカーの記録とバイト単位で一致しました",
        "de": "Testlauf: alle {n} Reports vom Löschen bis zum Start stimmen Byte für Byte mit dem Hersteller-Transkript überein",
        "fr": "essai à blanc : les {n} rapports de l'effacement au démarrage correspondent octet pour octet à la trace du fabricant",
        "es": "prueba sin grabar: los {n} informes desde el borrado hasta el inicio coinciden byte a byte con la traza del fabricante",
    },
    "in_app": {
        "en": "the keyboard is running its firmware; switching it to the bootloader (11 00)",
        "zh-TW": "鍵盤正在執行韌體;正在切換到啟動載入器 (11 00)",
        "ja": "キーボードはファームウェアで動作中です。ブートローダーに切り替えます (11 00)",
        "de": "Die Tastatur läuft mit ihrer Firmware; sie wird in den Bootloader umgeschaltet (11 00)",
        "fr": "le clavier exécute son firmware ; passage au bootloader (11 00)",
        "es": "el teclado ejecuta su firmware; cambiándolo al bootloader (11 00)",
    },
    "iap_timeout": {
        "en": "the bootloader (04D9:1407) did not appear within {s} s",
        "zh-TW": "啟動載入器 (04D9:1407) 在 {s} 秒內沒有出現",
        "ja": "ブートローダー (04D9:1407) が {s} 秒以内に現れませんでした",
        "de": "Der Bootloader (04D9:1407) ist innerhalb von {s} s nicht erschienen",
        "fr": "le bootloader (04D9:1407) n'est pas apparu en {s} s",
        "es": "el bootloader (04D9:1407) no apareció en {s} s",
    },
    "no_keyboard": {
        "en": "no USB keyboard in the bootloader or the firmware: {modes}",
        "zh-TW": "沒有處於啟動載入器或韌體模式的 USB 鍵盤:{modes}",
        "ja": "ブートローダーまたはファームウェアの USB キーボードが見つかりません: {modes}",
        "de": "Keine USB-Tastatur im Bootloader oder in der Firmware gefunden: {modes}",
        "fr": "aucun clavier USB dans le bootloader ou le firmware : {modes}",
        "es": "no hay teclado USB en el bootloader ni en el firmware: {modes}",
    },
    "modes_none": {
        "en": "nothing (keyboard off, unplugged or rebooting)",
        "zh-TW": "沒有任何裝置(鍵盤已關閉、未連接或正在重新啟動)",
        "ja": "何もありません(キーボードがオフ、未接続、または再起動中)",
        "de": "nichts (Tastatur aus, nicht angesteckt oder startet neu)",
        "fr": "rien (clavier éteint, débranché ou en cours de redémarrage)",
        "es": "nada (teclado apagado, desconectado o reiniciándose)",
    },
    "no_iap_iface": {
        "en": "the bootloader's update interface was not found; run: python -I tex_iap_probe.py list",
        "zh-TW": "找不到啟動載入器的更新介面;請執行:python -I tex_iap_probe.py list",
        "ja": "ブートローダーの更新インターフェースが見つかりません。実行: python -I tex_iap_probe.py list",
        "de": "Die Update-Schnittstelle des Bootloaders wurde nicht gefunden; ausführen: python -I tex_iap_probe.py list",
        "fr": "l'interface de mise à jour du bootloader est introuvable ; lancez : python -I tex_iap_probe.py list",
        "es": "no se encontró la interfaz de actualización del bootloader; ejecute: python -I tex_iap_probe.py list",
    },
    "no_update_iface": {
        "en": "no update interface for {name}; run: python -I tex_iap_probe.py list",
        "zh-TW": "找不到 {name} 的更新介面;請執行:python -I tex_iap_probe.py list",
        "ja": "{name} の更新インターフェースが見つかりません。実行: python -I tex_iap_probe.py list",
        "de": "Keine Update-Schnittstelle für {name}; ausführen: python -I tex_iap_probe.py list",
        "fr": "aucune interface de mise à jour pour {name} ; lancez : python -I tex_iap_probe.py list",
        "es": "no hay interfaz de actualización para {name}; ejecute: python -I tex_iap_probe.py list",
    },
    "need_mode": {
        "en": "needs {name}; present: {present}",
        "zh-TW": "需要 {name};目前偵測到:{present}",
        "ja": "{name} が必要です。検出されたもの: {present}",
        "de": "benötigt {name}; vorhanden: {present}",
        "fr": "nécessite {name} ; présent : {present}",
        "es": "necesita {name}; presente: {present}",
    },
    "vb_saved": {
        "en": "version block saved to {path}",
        "zh-TW": "版本區塊已儲存到 {path}",
        "ja": "バージョンブロックを {path} に保存しました",
        "de": "Versionsblock gespeichert in {path}",
        "fr": "bloc de version enregistré dans {path}",
        "es": "bloque de versión guardado en {path}",
    },
    "vb_save_failed": {
        "en": "warning: could not save the version block to {path} ({err}); the flash goes on without a saved copy",
        "zh-TW": "警告:無法將版本區塊儲存到 {path}({err});沒有備份副本,燒錄仍會繼續",
        "ja": "警告: バージョンブロックを {path} に保存できませんでした ({err})。保存コピーなしで書き込みを続けます",
        "de": "Warnung: Der Versionsblock konnte nicht in {path} gespeichert werden ({err}); das Flashen läuft ohne gespeicherte Kopie weiter",
        "fr": "avertissement : impossible d'enregistrer le bloc de version dans {path} ({err}) ; le flashage continue sans copie",
        "es": "aviso: no se pudo guardar el bloque de versión en {path} ({err}); la grabación sigue sin copia guardada",
    },
    "vb_blank_saved": {
        "en": "the keyboard's version block is blank; using the saved copy {path}",
        "zh-TW": "鍵盤的版本區塊是空白的;改用已儲存的副本 {path}",
        "ja": "キーボードのバージョンブロックが空です。保存済みのコピー {path} を使います",
        "de": "Der Versionsblock der Tastatur ist leer; die gespeicherte Kopie {path} wird verwendet",
        "fr": "le bloc de version du clavier est vide ; utilisation de la copie enregistrée {path}",
        "es": "el bloque de versión del teclado está en blanco; se usa la copia guardada {path}",
    },
    "vb_blank_none": {
        "en": "the keyboard's version block is blank and no saved copy exists; flash once with the vendor updater first",
        "zh-TW": "鍵盤的版本區塊是空白的,而且沒有已儲存的副本;請先用廠商的更新程式燒錄一次",
        "ja": "キーボードのバージョンブロックが空で、保存コピーもありません。先にメーカーのアップデータで一度書き込んでください",
        "de": "Der Versionsblock der Tastatur ist leer und es gibt keine gespeicherte Kopie; zuerst einmal mit dem Hersteller-Updater flashen",
        "fr": "le bloc de version du clavier est vide et aucune copie n'existe ; flashez d'abord une fois avec l'outil du fabricant",
        "es": "el bloque de versión del teclado está en blanco y no hay copia guardada; grabe antes una vez con el actualizador del fabricante",
    },
    "erasing": {
        "en": "erasing and writing",
        "zh-TW": "正在抹除並寫入",
        "ja": "消去して書き込み中",
        "de": "Löschen und Schreiben",
        "fr": "effacement et écriture",
        "es": "borrando y escribiendo",
    },
    "blocks": {
        "en": "  {done}/{total} blocks",
        "zh-TW": "  {done}/{total} 個區塊",
        "ja": "  {done}/{total} ブロック",
        "de": "  {done}/{total} Blöcke",
        "fr": "  {done}/{total} blocs",
        "es": "  {done}/{total} bloques",
    },
    "checksum_ok": {
        "en": "  checksum {sum} matches ({n} bytes written in {s} s)",
        "zh-TW": "  檢查碼 {sum} 相符(在 {s} 秒內寫入 {n} 位元組)",
        "ja": "  チェックサム {sum} が一致しました ({n} バイトを {s} 秒で書き込み)",
        "de": "  Prüfsumme {sum} stimmt überein ({n} Bytes in {s} s geschrieben)",
        "fr": "  somme de contrôle {sum} correcte ({n} octets écrits en {s} s)",
        "es": "  la suma de comprobación {sum} coincide ({n} bytes escritos en {s} s)",
    },
    "starting": {
        "en": "version block written and read back; starting the firmware (11 01)",
        "zh-TW": "版本區塊已寫入並讀回確認;正在啟動韌體 (11 01)",
        "ja": "バージョンブロックを書き込み、読み戻して確認しました。ファームウェアを起動します (11 01)",
        "de": "Versionsblock geschrieben und zurückgelesen; die Firmware wird gestartet (11 01)",
        "fr": "bloc de version écrit et relu ; démarrage du firmware (11 01)",
        "es": "bloque de versión escrito y releído; iniciando el firmware (11 01)",
    },
    "stopped": {
        "en": "stopped: {detail}. The keyboard stays in the bootloader; run this again, or run TEX's updater.",
        "zh-TW": "已停止:{detail}。鍵盤會停留在啟動載入器中;請再執行一次,或改用 TEX 的更新程式。",
        "ja": "停止しました: {detail}。キーボードはブートローダーのままです。もう一度実行するか、TEX のアップデータを実行してください。",
        "de": "Abgebrochen: {detail}. Die Tastatur bleibt im Bootloader; erneut ausführen oder den TEX-Updater starten.",
        "fr": "arrêté : {detail}. Le clavier reste dans le bootloader ; relancez ceci ou lancez l'outil de TEX.",
        "es": "detenido: {detail}. El teclado se queda en el bootloader; vuelva a ejecutar esto o use el actualizador de TEX.",
    },
    "watching": {
        "en": "watching USB for {s} s",
        "zh-TW": "監看 USB {s} 秒",
        "ja": "USB を {s} 秒間監視します",
        "de": "USB wird {s} s lang beobachtet",
        "fr": "surveillance de l'USB pendant {s} s",
        "es": "vigilando el USB durante {s} s",
    },
    "app_up": {
        "en": "the firmware is up (04D9:0407)",
        "zh-TW": "韌體已啟動 (04D9:0407)",
        "ja": "ファームウェアが起動しました (04D9:0407)",
        "de": "Die Firmware läuft (04D9:0407)",
        "fr": "le firmware est démarré (04D9:0407)",
        "es": "el firmware está en marcha (04D9:0407)",
    },
    "app_not_up": {
        "en": "the firmware did not come up as 04D9:0407 in that time (expected for canary builds, which return to the bootloader)",
        "zh-TW": "韌體在該時間內沒有以 04D9:0407 出現(canary 版本會回到啟動載入器,屬正常現象)",
        "ja": "その時間内にファームウェアが 04D9:0407 として現れませんでした(canary ビルドはブートローダーに戻るため想定どおりです)",
        "de": "Die Firmware ist in dieser Zeit nicht als 04D9:0407 erschienen (bei Canary-Builds normal, sie kehren in den Bootloader zurück)",
        "fr": "le firmware n'est pas apparu comme 04D9:0407 dans ce délai (normal pour les versions canary, qui reviennent au bootloader)",
        "es": "el firmware no apareció como 04D9:0407 en ese tiempo (esperable en las compilaciones canary, que vuelven al bootloader)",
    },
    "key_not_stock": {
        "en": "not TEX's stock AP_0407_4.04.exe (V1.04.04)",
        "zh-TW": "不是 TEX 原廠的 AP_0407_4.04.exe (V1.04.04)",
        "ja": "TEX 純正の AP_0407_4.04.exe (V1.04.04) ではありません",
        "de": "nicht TEXs originale AP_0407_4.04.exe (V1.04.04)",
        "fr": "ce n'est pas l'AP_0407_4.04.exe d'origine de TEX (V1.04.04)",
        "es": "no es el AP_0407_4.04.exe original de TEX (V1.04.04)",
    },
    "key_not_recovered": {
        "en": "could not recover the key from the updater",
        "zh-TW": "無法從更新程式取得金鑰",
        "ja": "アップデータから鍵を復元できませんでした",
        "de": "Der Schlüssel konnte nicht aus dem Updater gewonnen werden",
        "fr": "impossible de récupérer la clé depuis l'outil de mise à jour",
        "es": "no se pudo recuperar la clave del actualizador",
    },
    "key_load_failed": {
        "en": "{path}: {detail}; pass the 52-byte key file or TEX's AP_0407_4.04.exe",
        "zh-TW": "{path}:{detail};請提供 52 位元組的金鑰檔或 TEX 的 AP_0407_4.04.exe",
        "ja": "{path}: {detail}。52 バイトの鍵ファイルか TEX の AP_0407_4.04.exe を指定してください",
        "de": "{path}: {detail}; die 52-Byte-Schlüsseldatei oder TEXs AP_0407_4.04.exe angeben",
        "fr": "{path} : {detail} ; indiquez le fichier de clé de 52 octets ou l'AP_0407_4.04.exe de TEX",
        "es": "{path}: {detail}; indique el archivo de clave de 52 bytes o el AP_0407_4.04.exe de TEX",
    },
    "key_wrong": {
        "en": "{path}: not the TEX Shinobi key",
        "zh-TW": "{path}:不是 TEX Shinobi 的金鑰",
        "ja": "{path}: TEX Shinobi の鍵ではありません",
        "de": "{path}: nicht der Schlüssel des TEX Shinobi",
        "fr": "{path} : ce n'est pas la clé du TEX Shinobi",
        "es": "{path}: no es la clave del TEX Shinobi",
    },
    "cannot_read": {
        "en": "cannot read {path}: {err}",
        "zh-TW": "無法讀取 {path}:{err}",
        "ja": "{path} を読み込めません: {err}",
        "de": "{path} kann nicht gelesen werden: {err}",
        "fr": "impossible de lire {path} : {err}",
        "es": "no se puede leer {path}: {err}",
    },
    "image_size": {
        "en": "the image is {n} bytes; the bootloader takes at most {max}",
        "zh-TW": "映像檔為 {n} 位元組;啟動載入器最多接受 {max} 位元組",
        "ja": "イメージは {n} バイトです。ブートローダーが受け付けるのは最大 {max} バイトです",
        "de": "Das Image ist {n} Bytes groß; der Bootloader nimmt höchstens {max} an",
        "fr": "l'image fait {n} octets ; le bootloader en accepte au plus {max}",
        "es": "la imagen tiene {n} bytes; el bootloader admite como máximo {max}",
    },
    "image_sp": {
        "en": "the image's initial stack pointer {sp} is not in SRAM; this is not a Shinobi image",
        "zh-TW": "映像檔的初始堆疊指標 {sp} 不在 SRAM 內;這不是 Shinobi 的映像檔",
        "ja": "イメージの初期スタックポインタ {sp} が SRAM 内にありません。Shinobi 用のイメージではありません",
        "de": "Der Anfangs-Stackpointer {sp} des Images liegt nicht im SRAM; das ist kein Shinobi-Image",
        "fr": "le pointeur de pile initial {sp} de l'image n'est pas dans la SRAM ; ce n'est pas une image Shinobi",
        "es": "el puntero de pila inicial {sp} de la imagen no está en la SRAM; no es una imagen de Shinobi",
    },
    "image_reset": {
        "en": "the reset vector {reset} is not a Thumb address inside the image linked at {base}",
        "zh-TW": "重設向量 {reset} 不是位於連結於 {base} 之映像檔內的 Thumb 位址",
        "ja": "リセットベクタ {reset} は、{base} にリンクされたイメージ内の Thumb アドレスではありません",
        "de": "Der Reset-Vektor {reset} ist keine Thumb-Adresse innerhalb des auf {base} gelinkten Images",
        "fr": "le vecteur de reset {reset} n'est pas une adresse Thumb dans l'image liée à {base}",
        "es": "el vector de reinicio {reset} no es una dirección Thumb dentro de la imagen enlazada en {base}",
    },
    "image_record": {
        "en": "the image lacks TEX's record at {at}; the bootloader would refuse to checksum it",
        "zh-TW": "映像檔在 {at} 缺少 TEX 的紀錄;啟動載入器會拒絕計算其檢查碼",
        "ja": "イメージの {at} に TEX のレコードがありません。ブートローダーはチェックサムを拒否します",
        "de": "Dem Image fehlt TEXs Datensatz bei {at}; der Bootloader würde die Prüfsumme verweigern",
        "fr": "il manque l'enregistrement de TEX à {at} dans l'image ; le bootloader refuserait la somme de contrôle",
        "es": "a la imagen le falta el registro de TEX en {at}; el bootloader rechazaría la suma de comprobación",
    },
    "hid_missing": {
        "en": "the Python hidapi package is not installed ({err}). {hint}",
        "zh-TW": "尚未安裝 Python 的 hidapi 套件({err})。{hint}",
        "ja": "Python の hidapi パッケージがインストールされていません ({err})。{hint}",
        "de": "Das Python-Paket hidapi ist nicht installiert ({err}). {hint}",
        "fr": "le paquet Python hidapi n'est pas installé ({err}). {hint}",
        "es": "el paquete hidapi de Python no está instalado ({err}). {hint}",
    },
    "open_failed_unix": {
        "en": "cannot open the keyboard ({err}). This is usually a missing permission rule; see {doc}",
        "zh-TW": "無法開啟鍵盤({err})。通常是缺少權限規則;請參閱 {doc}",
        "ja": "キーボードを開けません ({err})。多くの場合、権限ルールがありません。{doc} を参照してください",
        "de": "Die Tastatur kann nicht geöffnet werden ({err}). Meist fehlt eine Berechtigungsregel; siehe {doc}",
        "fr": "impossible d'ouvrir le clavier ({err}). Il manque en général une règle de permissions ; voir {doc}",
        "es": "no se puede abrir el teclado ({err}). Suele faltar una regla de permisos; consulte {doc}",
    },
    "open_failed_win": {
        "en": "cannot open the keyboard ({err}). Close TEX's updater and any other program using it, then try again",
        "zh-TW": "無法開啟鍵盤({err})。請關閉 TEX 的更新程式與其他使用鍵盤的程式後再試",
        "ja": "キーボードを開けません ({err})。TEX のアップデータなど、使用中の他のプログラムを閉じてからやり直してください",
        "de": "Die Tastatur kann nicht geöffnet werden ({err}). TEXs Updater und andere Programme, die sie nutzen, schließen und erneut versuchen",
        "fr": "impossible d'ouvrir le clavier ({err}). Fermez l'outil de TEX et tout autre programme qui l'utilise, puis réessayez",
        "es": "no se puede abrir el teclado ({err}). Cierre el actualizador de TEX y cualquier otro programa que lo use, y vuelva a intentarlo",
    },
}

_current = DEFAULT


def set_language(lang):
    global _current
    if lang not in LANGS:
        raise ValueError(f"unsupported language {lang!r}")
    _current = lang


def current():
    return _current


def t(key, in_lang=None, **values):
    """The message `key` in the current (or given) language with its {placeholders} filled in."""
    return MESSAGES[key][in_lang or _current].format(**values)


def normalize(tag):
    """Map a locale or language tag (zh_TW.UTF-8, ja-JP, de_DE@euro, zh-Hant, fr) to one of LANGS, else None.

    Only Traditional Chinese is provided: zh-TW/HK/MO and the Hant script, and a bare 'zh', map to it;
    zh-CN/SG and the Hans script do not (they fall back like any unsupported language)."""
    if not tag:
        return None
    base = tag.strip().lower().split(".")[0].split("@")[0]
    parts = [p for p in base.replace("-", "_").split("_") if p]
    if not parts:
        return None
    primary, rest = parts[0], set(parts[1:])
    if primary == "zh":
        if rest & {"cn", "sg", "hans"}:
            return None
        return "zh-TW"
    return primary if primary in ("en", "ja", "de", "fr", "es") else None


def _windows_ui_language():
    """The Windows user UI language as a tag, or None (not Windows, or the call failed)."""
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError, ImportError):
        return None
    primary = langid & 0x3FF
    if primary == 0x04:  # Chinese: 0x0404 Taiwan, 0x0C04 Hong Kong, 0x1404 Macao are Traditional
        return "zh_TW" if langid in (0x0404, 0x0C04, 0x1404) else "zh_CN"
    return {0x09: "en", 0x11: "ja", 0x07: "de", 0x0C: "fr", 0x0A: "es"}.get(primary)


def from_environment(environ=None, windows_ui=None):
    """The language the locale asks for, or None. environ defaults to os.environ; windows_ui is a tag (tests)."""
    env = os.environ if environ is None else environ
    base = next((env[k] for k in ("LC_ALL", "LC_MESSAGES", "LANG") if env.get(k)), "")
    if base and base.split(".")[0].split("@")[0] in ("C", "POSIX"):
        return "en"  # GNU gettext: with the C locale, LANGUAGE is ignored too
    for tag in env.get("LANGUAGE", "").split(":") if base else []:
        lang = normalize(tag)
        if lang:
            return lang
    lang = normalize(base)
    if lang:
        return lang
    ui = windows_ui if windows_ui is not None else (_windows_ui_language() if sys.platform == "win32" else None)
    return normalize(ui)


def encodable(lang, encoding):
    """Whether every message in `lang` can be written in `encoding`."""
    try:
        for msg in MESSAGES.values():
            msg[lang].encode(encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def pick(requested=None, environ=None, encoding=None, windows_ui=None):
    """(language, note): the --lang value, else the locale, else English; English when `encoding` cannot show it.

    note is an English line to print when an explicit request or the locale had to be dropped, else None."""
    lang = normalize(requested) if requested else from_environment(environ, windows_ui)
    lang = lang or DEFAULT
    if encoding is not None and lang != DEFAULT and not encodable(lang, encoding):
        return DEFAULT, t("lang_fallback", in_lang=DEFAULT, enc=encoding, lang=lang)
    return lang, None


def setup(requested=None):
    """Choose the language for this process from --lang / the locale and the stdout encoding; never raises
    on unencodable output afterwards (errors='replace')."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    lang, note = pick(requested, encoding=getattr(sys.stdout, "encoding", None))
    set_language(lang)
    if note:
        print(note, file=sys.stderr)
    return lang
