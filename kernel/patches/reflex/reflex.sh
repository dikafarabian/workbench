#!/usr/bin/env bash

# ======================================================
# ⚡ PATCH — Reflex (CPUFreq governor)
# ======================================================

REFLEX_PATCH="${ROOT_DIR}/kernel/patches/reflex/${KERNEL_VERSION}/reflex-v0.4.0.patch"
[ -f "$REFLEX_PATCH" ] || REFLEX_PATCH="${ROOT_DIR}/kernel/patches/reflex/reflex-v0.4.0.patch"

log "⚡ Applying Reflex CPUFreq governor patch..."
apply_patch "Reflex" "$REFLEX_PATCH" "$KERNEL_SRC" --fuzz=3
gki_defconfig_enable CONFIG_CPU_FREQ_GOV_REFLEX

REFLEX_VERSION="$(basename "$REFLEX_PATCH" .patch | sed 's/^reflex-//')"

log "Reflex CPUFreq governor integrated ✅"
