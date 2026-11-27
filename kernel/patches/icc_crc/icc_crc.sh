#!/usr/bin/env bash

# ======================================================
# 🧬 PATCH — icc_path KMI CRC preservation
# ======================================================
# Keeps the icc_path symbol CRC identical to Clang 18 stock modules
# Source: https://github.com/riza220201/poco-f7-kernel

ICC_CRC_PATCH="${ROOT_DIR}/kernel/patches/icc_crc/icc-crc.patch"

log "🧬 Applying icc_path CRC preservation patch..."
apply_patch "icc_path CRC" "$ICC_CRC_PATCH" "$KERNEL_SRC" --fuzz=3

log "icc_path CRC preserved ✅"
