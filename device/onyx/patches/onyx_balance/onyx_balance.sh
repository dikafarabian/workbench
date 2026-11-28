#!/usr/bin/env bash

# ======================================================
# 🎯 PATCH — onyx_balance (SM8735 CPUFreq policy)
# ======================================================
# Source: https://github.com/riza220201/poco-f7-kernel

ONYX_BALANCE_PATCH="${ROOT_DIR}/device/onyx/patches/onyx_balance/onyx_balance-v7.patch"

log "🎯 Applying onyx_balance CPUFreq policy patch..."
apply_patch "onyx_balance" "$ONYX_BALANCE_PATCH" "$KERNEL_SRC" --fuzz=3
gki_defconfig_enable CONFIG_ONYX_BALANCE

ONYX_BALANCE_VERSION="$(basename "$ONYX_BALANCE_PATCH" .patch | sed 's/^onyx_balance-//')"

log "onyx_balance integrated ✅"
