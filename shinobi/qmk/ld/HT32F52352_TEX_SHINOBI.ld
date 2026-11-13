/*
 * Adapted from keyboards/annepro2/ld/HT32F52352_ANNEPRO2_C18.ld (MIT):
 * Copyright (c) 2013-2016 Fabio Utzig, (c) 2020 Yaotian Feng (Codetector),
 * (c) 2025 Michal Kopec. See that file for the full MIT notice.
 *
 * TEX Shinobi: the stock IAP owns 0x0000-0x2FFF and its version block sits at
 * 0x3000; the app vector table is at 0x3200 (stock VTOR). The stock app keeps
 * its stack below 0x20003FE0 and the IAP magic word lives at 0x20003FFC, so
 * RAM stops at 0x20003FE0 too. Flash length assumes a 64 KB part.
 *
 * ChibiOS aligns .vectors to 1 KB by default, which would push the table to
 * 0x3400 where the IAP does not look. The Cortex-M0+ VTOR only needs the
 * table size rounded up to a power of two (48 vectors -> 256 bytes).
 *
 * Stock keeps a 12-byte record at 0x3BF8, between two functions. Without it the
 * IAP answers the updater's checksum query (`1D 01`) with 0 and the flash fails
 * (PORT_NOTES.md, "Flashing": every image without it failed, the full QMK canary
 * with it patched in passed). Its fields are not decoded; the first word
 * matches the IAP's `12 00` reply. The IAP takes images up to 28,076 bytes
 * (rules.mk), so the 2.3 KB gap below the record is used: the vectors, the
 * unwind table and the .data image in flash0, the sequence macros in flash0m, the
 * keymaps in flash0b. Code and
 * the other constants follow the record in flash2.
 */
__vectors_align__ = 256;
MEMORY {
    flash0   : org = 0x00003200, len = 0x37A0 - 0x3200 /* vectors, unwind table, data image */
    flash0m  : org = 0x000037A0, len = 96              /* sequence macros */
    flash0b  : org = 0x00003800, len = 0x3BF8 - 0x3800 /* keymaps */
    flash1   : org = 0x00003BF8, len = 12              /* stock app record */
    flash2   : org = 0x00003C04, len = 64k - 0x3C04    /* code, constants */
    flash3   : org = 0x00000000, len = 0
    flash4   : org = 0x00000000, len = 0
    flash5   : org = 0x00000000, len = 0
    flash6   : org = 0x00000000, len = 0
    flash7   : org = 0x00000000, len = 0
    ram0     : org = 0x20000000, len = 16k - 32        /* RAM */
    ram1     : org = 0x00000000, len = 0
    ram2     : org = 0x00000000, len = 0
    ram3     : org = 0x00000000, len = 0
    ram4     : org = 0x00000000, len = 0
    ram5     : org = 0x00000000, len = 0
    ram6     : org = 0x00000000, len = 0
    ram7     : org = 0x00000000, len = 0
}

REGION_ALIAS("VECTORS_FLASH", flash0);
REGION_ALIAS("VECTORS_FLASH_LMA", flash0);
REGION_ALIAS("XTORS_FLASH", flash0);
REGION_ALIAS("XTORS_FLASH_LMA", flash0);
REGION_ALIAS("TEXT_FLASH", flash2);
REGION_ALIAS("TEXT_FLASH_LMA", flash2);
REGION_ALIAS("RODATA_FLASH", flash2);
REGION_ALIAS("RODATA_FLASH_LMA", flash2);
REGION_ALIAS("VARIOUS_FLASH", flash0);
REGION_ALIAS("VARIOUS_FLASH_LMA", flash0);
REGION_ALIAS("RAM_INIT_FLASH_LMA", flash0);
REGION_ALIAS("MAIN_STACK_RAM", ram0);
REGION_ALIAS("PROCESS_STACK_RAM", ram0);
REGION_ALIAS("DATA_RAM", ram0);
REGION_ALIAS("DATA_RAM_LMA", flash0);
REGION_ALIAS("BSS_RAM", ram0);
REGION_ALIAS("HEAP_RAM", ram0);

SECTIONS {
    /* Ahead of rules.ld so its .rodata doesn't claim the keymaps first. */
    .tex_keymaps : ALIGN(4) {
        *(.rodata.keymaps)
    } > flash0b

    /* Code that fills the gap between the keymaps and the record (section attribute in shinobi.c). */
    .tex_text0b : {
        *(.tex_text0b)
    } > flash0b

    /* Sequence macros (power.c macro_play) at a fixed address, so the keymap editor can patch them. A keymap
       may fill them from C (tex_macro_data in section .tex_macros, as the editor exports it); the rest is zero.
       power.c reads them through these linker symbols, so the compiler never sees their contents. */
    .tex_macros : {
        tex_macros = .;
        KEEP(*(.tex_macros))
        . = tex_macros + 96;
        tex_macros_end = .;
    } > flash0m

    .tex_app_record : {
        LONG(0x04045100) LONG(0x34000001) LONG(0x00020004)
    } > flash1
}

INCLUDE rules.ld

/* After rules.ld, so these follow the vectors and the .data image in flash0: constants beyond flash2's room
   (section attribute in power.c). */
SECTIONS {
    .tex_rodata0 : {
        *(.tex_rodata0)
    } > flash0
}
