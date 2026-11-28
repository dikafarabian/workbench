#!/usr/bin/env bash

# ======================================================
# 🔋 PATCH — MCA bypass charging (Xiaomi MCA modules)
# ======================================================
# Live-patches mca_* vendor modules at load time and overrides MCA input limits
# Source: https://github.com/erllanggod/88days (main/etc/kabi/mca-bypass.patch, unmodified)

MCA_BYPASS_PATCH="${ROOT_DIR}/device/onyx/patches/bypasscharging/mca-bypass.patch"

log "🔋 Applying MCA bypass charging patch..."
apply_patch "MCA bypass charging" "$MCA_BYPASS_PATCH" "$KERNEL_SRC" --fuzz=3
gki_defconfig_enable CONFIG_MCA_BYPASS

log "MCA bypass charging integrated ✅"
