#!/usr/bin/env bash

# ======================================================
# ⚙️ PATCH — Kcompressd
# ======================================================

KCOMPRESSD_PATCH="${ROOT_DIR}/kernel/patches/kcompressd/${KERNEL_VERSION}/kcompressd-v0.5.patch"
[ -f "$KCOMPRESSD_PATCH" ] || KCOMPRESSD_PATCH="${ROOT_DIR}/kernel/patches/kcompressd/kcompressd-v0.5.patch"

log "⚙️ Applying Kcompressd patch..."
apply_patch "kcompressd" "$KCOMPRESSD_PATCH" "$KERNEL_SRC" --fuzz=3
if grep -q '^config KCOMPRESSD' "${KERNEL_SRC}/mm/Kconfig"; then
    gki_defconfig_enable CONFIG_KCOMPRESSD CONFIG_CRYPTO_LZ4HC
fi

KCOMPRESSD_VERSION="$(basename "$KCOMPRESSD_PATCH" .patch | sed 's/^kcompressd-//')"

log "Kcompressd integrated ✅"
