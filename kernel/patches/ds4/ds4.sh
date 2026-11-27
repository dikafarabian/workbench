#!/usr/bin/env bash

# ======================================================
# 🎮 PATCH — DualShock 4 clone fallbacks (hid-playstation)
# ======================================================
# Source: https://github.com/riza220201/poco-f7-kernel

DS4_PATCH="${ROOT_DIR}/kernel/patches/ds4/ds4-clones.patch"

log "🎮 Applying DualShock 4 clone fallback patch..."
apply_patch "DS4 clones" "$DS4_PATCH" "$KERNEL_SRC" --fuzz=3

log "DualShock 4 clone fallback integrated ✅"
