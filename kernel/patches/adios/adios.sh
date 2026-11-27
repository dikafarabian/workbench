#!/usr/bin/env bash

# ======================================================
# 💾 PATCH — ADIOS (I/O scheduler)
# ======================================================

ADIOS_PATCH="${ROOT_DIR}/kernel/patches/adios/${KERNEL_VERSION}/adios-v3.3.0.patch"
[ -f "$ADIOS_PATCH" ] || ADIOS_PATCH="${ROOT_DIR}/kernel/patches/adios/adios-v3.3.0.patch"

log "💾 Applying ADIOS I/O scheduler patch..."
apply_patch "ADIOS" "$ADIOS_PATCH" "$KERNEL_SRC" --fuzz=3
gki_defconfig_enable CONFIG_MQ_IOSCHED_ADIOS

ADIOS_VERSION="$(basename "$ADIOS_PATCH" .patch | sed 's/^adios-//')"

log "ADIOS I/O scheduler integrated ✅"
