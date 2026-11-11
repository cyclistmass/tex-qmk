# Test build: full QMK that hands back to the stock IAP after 600 s (10 min) of uptime.
OPT_DEFS += -DTEX_TEST_TIMEOUT_S=600
