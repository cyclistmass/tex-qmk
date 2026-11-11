# Test build: test600 plus a read-only 13 00 query on the vendor interface that returns main-loop
# passes, uptime, the debounced matrix and raw port inputs (tools/tex_iap_probe.py matrix).
OPT_DEFS += -DTEX_TEST_TIMEOUT_S=600 -DTEX_DIAG
