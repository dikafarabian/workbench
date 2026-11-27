#!/usr/bin/env bash

# ======================================================
# ↩️ PATCH — arm64 no-map linear mapping revert
# ======================================================
# Reverts "arm64: mm: fix accidental linear mapping of no-map reserved memory"
# Already absent on sources that don't carry the change

NOMAP_REVERT_PATCH="${ROOT_DIR}/kernel/patches/nomap_revert/nomap_revert.patch"

log "↩️ Reverting arm64 no-map linear mapping change..."
apply_patch "No-map revert" "$NOMAP_REVERT_PATCH" "$KERNEL_SRC"

log "arm64 no-map linear mapping change reverted ✅"
