# Test build: enters the stock IAP from __early_init, before clock setup.
# Proves the IAP starts the image at 0x3200; expect the keyboard in 04D9:1407.
OPT_DEFS += -DTEX_CANARY
