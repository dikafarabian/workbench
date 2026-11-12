#!/usr/bin/env bash

# ======================================================
# 🔑 ROOT SOLUTION — MidoriSU
# ======================================================
# Repo: https://github.com/midori01/KernelSU (main)

KSU_DIR="${KERNEL_SRC}/KernelSU"

MIDORISU_SETUP_URL="https://raw.githubusercontent.com/midori01/KernelSU/main/kernel/setup.sh"

ksu_integrate "MidoriSU" "$MIDORISU_SETUP_URL" "${MIDORISU_REF:-main}" midorisu

log "Branding skipped (MidoriSU ships its own manager identity) ✅"

ksu_git_version "v0.1.0" 999
ksu_publish_version
ksu_enable_configs CONFIG_KSU

log "MidoriSU ready ✅"
