# MCU: Holtek HT32F52352 Cortex-M0+ (see boards/TEX_SHINOBI/board.h)
MCU = cortex-m0plus
ARMV = 6
USE_FPU = no
MCU_FAMILY = HT32
MCU_SERIES = HT32F523xx
MCU_LDSCRIPT = HT32F52352_TEX_SHINOBI
MCU_STARTUP = ht32f523xx

BOARD = TEX_SHINOBI

# The stock IAP at 0x0000-0x2FFF stays; bootloader_jump() hands over to it.
BOOTLOADER = custom

# PS/2: ps2_vendor.c, QMK's busywait driver with stream-mode receive. The vendor
# driver type does not pull in the pin helpers by itself.
SRC += ps2_io.c

# Bluetooth: the BLE board's nRF52810 module on USART0 (ble.c).
BLUETOOTH_ENABLE = yes
BLUETOOTH_DRIVER = custom
SRC += ble.c

# Battery level and sleep on battery (power.c).
SRC += power.c
# Signed division in 28 bytes for libgcc's 460 (the image limit); see divsi3.S.
SRC += divsi3.S

# The app's vectors are at 0x3200, not 0. Stock points VTOR there itself
# (FUN_34ec), so the IAP is not relied on to do it.
ADEFS += -DCRT0_VTOR_INIT=1

# The IAP takes images up to the stock app's 28,076 bytes (tools/build_updater.py
# SLOT); QMK features the stock keymap has no use for stay out.
LTO_ENABLE = yes
SPACE_CADET_ENABLE = no
GRAVE_ESC_ENABLE = no
MAGIC_ENABLE = no
# Matrix mouse buttons 1-3 reach the PS/2 report without mousekey (tp_buttons).
MOUSEKEY_ENABLE = no
# ChibiOS keeps a table of 8 RAM areas to initialise; this board has one.
OPT_DEFS += -DCRT0_AREAS_NUMBER=1
