#!/usr/bin/env bash

# ======================================================
# 🔑 ROOT SOLUTION — FinaSU
# ======================================================
# Repo: https://github.com/LyraVoid/FinaSU

KSU_DIR="${KERNEL_SRC}/FinaSU"

ksu_integrate "FinaSU" "https://raw.githubusercontent.com/LyraVoid/FinaSU/dev/kernel/setup.sh" "${FINASU_REF:-}" finasu

FINASU_MANAGER_SIGNATURE_SIZE="0x2cc"
FINASU_MANAGER_SIGNATURE_HASH="2d89b50aaf1db013c2b6738f973f48b62ea21a3a8d7216bfec3521065d448458"

sed -i \
    -e "s|^KSU_EXPECTED_SIZE := .*|KSU_EXPECTED_SIZE := ${FINASU_MANAGER_SIGNATURE_SIZE}|" \
    -e "s|^KSU_EXPECTED_HASH := .*|KSU_EXPECTED_HASH := ${FINASU_MANAGER_SIGNATURE_HASH}|" \
    "${KSU_DIR}/kernel/Kbuild"

grep -q "^KSU_EXPECTED_SIZE := ${FINASU_MANAGER_SIGNATURE_SIZE}$" "${KSU_DIR}/kernel/Kbuild" \
    && grep -q "^KSU_EXPECTED_HASH := ${FINASU_MANAGER_SIGNATURE_HASH}$" "${KSU_DIR}/kernel/Kbuild" \
    || error "FinaSU manager signature patch failed!"

log "Manager signature set to FinaSU release key ✅"

log "Branding skipped (FinaSU exposes no Luminaire version field) ✅"

ksu_git_version "v0.1.0"
ksu_publish_version
ksu_enable_configs CONFIG_KSU

log "FinaSU ready ✅"
