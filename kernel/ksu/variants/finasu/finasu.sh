#!/usr/bin/env bash

# ======================================================
# 🔑 ROOT SOLUTION — FinaSU
# ======================================================
# Repo: https://github.com/LyraVoid/FinaSU

KSU_DIR="${KERNEL_SRC}/FinaSU"

ksu_integrate "FinaSU" "https://raw.githubusercontent.com/LyraVoid/FinaSU/dev/kernel/setup.sh" "${FINASU_REF:-}" finasu

log "Branding skipped (FinaSU exposes no Luminaire version field) ✅"

ksu_git_version "v0.1.0"
ksu_publish_version
ksu_enable_configs CONFIG_KSU

log "FinaSU ready ✅"
