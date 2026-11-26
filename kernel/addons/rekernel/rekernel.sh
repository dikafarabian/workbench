#!/usr/bin/env bash

# ======================================================
# 📦 ADDON — Re:Kernel + Re:Kernel-X (Binder/Signal Netlink servers)
# ======================================================
# Repo: https://github.com/Sakion-Team/Re-Kernel
# Repo: https://github.com/myflavor/ReKernel-X
# Integration: built-in drivers from each repo's LKM-Source (latest tag)
# ======================================================

REKERNEL_REPO="https://github.com/Sakion-Team/Re-Kernel"
REKERNEL_X_REPO="https://github.com/myflavor/ReKernel-X"

clone_latest_tag() {
    local repo="$1" dir="$2" tag
    retry 3 run_quiet git clone --filter=blob:none "$repo" "$dir" || return 1
    tag="$(git -C "$dir" describe --tags "$(git -C "$dir" rev-list --tags -n 1)")" || return 1
    git -C "$dir" checkout -q "tags/${tag}" || return 1
    echo "$tag"
}

log "Fetching Re:Kernel sources..."
REKERNEL_WORK="$(mktemp -d)"
REKERNEL_TAG="$(clone_latest_tag "$REKERNEL_REPO" "${REKERNEL_WORK}/ReKernel")" \
    || { addon_skip "Re:Kernel clone failed — skipping"; rm -rf "$REKERNEL_WORK"; return 0; }
REKERNEL_X_TAG="$(clone_latest_tag "$REKERNEL_X_REPO" "${REKERNEL_WORK}/ReKernel_X")" \
    || { addon_skip "Re:Kernel-X clone failed — skipping"; rm -rf "$REKERNEL_WORK"; return 0; }
log "Re:Kernel ${REKERNEL_TAG} | Re:Kernel-X ${REKERNEL_X_TAG}"

DRIVERS_DIR="${KERNEL_SRC}/drivers"

log "Integrating Re:Kernel (built-in)..."
cp -r "${REKERNEL_WORK}/ReKernel/LKM-Source" "${DRIVERS_DIR}/rekernel"
sed -i "s/obj-m := rekernel.o/obj-\$(CONFIG_REKERNEL) += rekernel.o/" "${DRIVERS_DIR}/rekernel/Makefile"
echo "obj-\$(CONFIG_REKERNEL) += rekernel/" >> "${DRIVERS_DIR}/Makefile"
grep -q "drivers/rekernel/Kconfig" "${DRIVERS_DIR}/Kconfig" \
    || sed -i '/endmenu/i source "drivers/rekernel/Kconfig"' "${DRIVERS_DIR}/Kconfig"

log "Integrating Re:Kernel-X (built-in)..."
cp -r "${REKERNEL_WORK}/ReKernel_X/LKM-Source" "${DRIVERS_DIR}/rekernel_x"
sed -i 's/\bstart_rekernel\b/rkx_start/g; s/\bexit_rekernel\b/rkx_exit/g; s/\bsendMessage\b/rkx_sendMessage/g; s/\bnet_uid_add\b/rkx_net_uid_add/g; s/\bnet_uid_del\b/rkx_net_uid_del/g; s/\bregister_signal\b/rkx_register_signal/g; s/\bunregister_signal\b/rkx_unregister_signal/g; s/\bregister_netfilter\b/rkx_register_netfilter/g; s/\bunregister_netfilter\b/rkx_unregister_netfilter/g; s/\bregister_binder\b/rkx_register_binder/g; s/\bunregister_binder\b/rkx_unregister_binder/g' "${DRIVERS_DIR}"/rekernel_x/*.{c,h}
sed -i 's/obj-m += rekernel_x.o/obj-y += rekernel_x.o/' "${DRIVERS_DIR}/rekernel_x/Makefile"
echo 'obj-y += rekernel_x/' >> "${DRIVERS_DIR}/Makefile"
rm -rf "$REKERNEL_WORK"

if [ ! -f "${DRIVERS_DIR}/rekernel/Makefile" ] \
        || ! grep -qF "obj-\$(CONFIG_REKERNEL) += rekernel.o" "${DRIVERS_DIR}/rekernel/Makefile" \
        || ! grep -q 'obj-y += rekernel_x.o' "${DRIVERS_DIR}/rekernel_x/Makefile" \
        || ! grep -q 'source "drivers/rekernel/Kconfig"' "${DRIVERS_DIR}/Kconfig"; then
    error "Re:Kernel integration incomplete — build would silently lack Re:Kernel!"
fi

gki_defconfig_enable CONFIG_REKERNEL CONFIG_REKERNEL_NETWORK CONFIG_REKERNEL_LEGACY_NETLINK

export RKX_VERSION="v${REKERNEL_X_TAG}"
REKERNEL_VERSION="${REKERNEL_TAG} + RKX ${RKX_VERSION}"

log "Re:Kernel integrated ✅"
