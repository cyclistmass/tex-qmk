# Test build: like canary, but spins before entering the stock IAP: about 5 s if the IAP hands over at
# 48 MHz, about 28 s at the 8 MHz reset clock. After `11 01` the keyboard stays off USB that long,
# which an IAP with no app to start cannot do (it re-enumerates within about 1 s).
OPT_DEFS += -DTEX_CANARY -DTEX_CANARY_SPIN=16000000UL
# The firmware after __early_init never runs in this build; NKRO off keeps it within the IAP's 28,076 bytes.
NKRO_ENABLE = no
