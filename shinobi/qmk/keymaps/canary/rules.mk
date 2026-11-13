# Test build: enters the stock IAP from __early_init, before clock setup.
# Proves the IAP starts the image at 0x3200; expect the keyboard in 04D9:1407.
OPT_DEFS += -DTEX_CANARY
# The firmware after __early_init never runs in this build; NKRO off keeps it within the IAP's 28,076 bytes.
NKRO_ENABLE = no
