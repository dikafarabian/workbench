#!/usr/bin/env bash

# ======================================================
# 🔥 PATCH — BORE (CPU scheduler)
# ======================================================
# 6.6: from riza220201/poco-f7-kernel, state split across task_struct slot 3
# and sched_entity slots 1-4 so task_struct slots 6-8 stay free for SysV IPC
# ======================================================

BORE_PATCH="${ROOT_DIR}/kernel/patches/bore/${KERNEL_VERSION}/bore-v7.0.1.patch"
[ -f "$BORE_PATCH" ] || BORE_PATCH="${ROOT_DIR}/kernel/patches/bore/bore-v7.0.0.patch"

log "🔥 Applying BORE CPU scheduler patch..."
apply_patch "BORE" "$BORE_PATCH" "$KERNEL_SRC" --fuzz=3
gki_defconfig_enable CONFIG_SCHED_BORE

BORE_VERSION="$(basename "$BORE_PATCH" .patch | sed 's/^bore-//')"

log "BORE CPU scheduler integrated ✅"
