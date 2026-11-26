#!/usr/bin/env bash

# ======================================================
# 🔑 ROOT SOLUTION — MidoriSU
# ======================================================
# Base: https://github.com/KOWX712/KernelSU (master)
# Setup and extras follow https://github.com/midori01/gki_ksu_workflow

KSU_DIR="${KERNEL_SRC}/KernelSU"

MIDORISU_REPO="midori01/KernelSU"
MIDORISU_SETUP_SCRIPT_URL="https://raw.githubusercontent.com/midori01/gki_ksu_workflow/main/.github/scripts/setup_ksu.sh"
MIDORISU_VERSION_BASE=30999

ksu_integrate "MidoriSU" "https://raw.githubusercontent.com/KOWX712/KernelSU/main/kernel/setup.sh" "${MIDORISU_REF:-}" midorisu

MIDORISU_COMMIT_COUNT="$(github_commit_count "$MIDORISU_REPO" main)"
[ -n "$MIDORISU_COMMIT_COUNT" ] || warn "MidoriSU: commit count unavailable — version code falls back to ${MIDORISU_VERSION_BASE}"
KSU_VERSION_CODE=$((MIDORISU_VERSION_BASE + ${MIDORISU_COMMIT_COUNT:-0}))
KSU_TAG_NAME="$(git -C "$KSU_DIR" describe --tags --abbrev=0 2>/dev/null || echo "v0.1.0")"

MIDORISU_SETUP_SCRIPT="$(fetch "$MIDORISU_SETUP_SCRIPT_URL")" || error "MidoriSU: failed to download setup_ksu.sh!"
grep -q "^#!" <<< "$MIDORISU_SETUP_SCRIPT" || error "MidoriSU: setup_ksu.sh looks invalid (no shebang)!"
(cd "$KERNEL_SRC" && KSU_VERSION="$KSU_VERSION_CODE" bash <<< "$MIDORISU_SETUP_SCRIPT") || error "MidoriSU: setup_ksu.sh failed!"
log "MidoriSU: manager and version set up ✅"

ksu_apply_pinned_commit midorisu_kow 2 "MidoriSU extras (temp fix)"
ksu_apply_pinned_commit midorisu_kow 1 "MidoriSU extras"

log "Branding skipped (MidoriSU ships its own manager identity) ✅"

ksu_publish_version
ksu_enable_configs CONFIG_KSU

log "MidoriSU ready ✅"
