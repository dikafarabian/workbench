#!/usr/bin/env bash

# ======================================================
# 🚀 PATCH — BBRv3
# TCP congestion control backport by fatalcoder524
# Patch source: https://github.com/WildKernels/kernel_patches
# android14-6.1-lts: GKI-layout-preserving adaptation from midori01/gki_ksu_workflow
# ======================================================

BBRV3_PATCHES_BASE="https://github.com/WildKernels/kernel_patches/raw/main/common/bbrv3"

BBRV3_LOCAL_PATCH="${ROOT_DIR}/kernel/patches/bbrv3/${KERNEL_BRANCH}.patch"

if [ -f "${BBRV3_LOCAL_PATCH}" ]; then
    log "🚀 Applying BBRv3 patch (local ${KERNEL_BRANCH})..."
    apply_patch "BBRv3" "${BBRV3_LOCAL_PATCH}" "$KERNEL_SRC" --fuzz=0
else
    BBRV3_PATCH="0001-net-tcp-backport-BBRv3-to-${ANDROID_VERSION}-${KERNEL_VERSION}.patch"

    BBRV3_SYSCTL_SOURCE="${KERNEL_SRC}/net/ipv4/sysctl_net_ipv4.c"
    TCP_MIN_RCVBUF_DECL="static int tcp_min_rcvbuf = 4096;"
    TCP_MIN_RCVBUF_DETACHED=false

    if grep -qxF "${TCP_MIN_RCVBUF_DECL}" "${BBRV3_SYSCTL_SOURCE}"; then
        sed -i "/^${TCP_MIN_RCVBUF_DECL}\$/,+1d" "${BBRV3_SYSCTL_SOURCE}"
        TCP_MIN_RCVBUF_DETACHED=true
    fi

    log "🚀 Applying BBRv3 patch (${BBRV3_PATCH})..."
    apply_remote_patch "BBRv3" "${BBRV3_PATCHES_BASE}/${BBRV3_PATCH}" "$KERNEL_SRC"

    if [ "${TCP_MIN_RCVBUF_DETACHED}" = true ]; then
        sed -i "s|^/\* obsolete \*/\$|${TCP_MIN_RCVBUF_DECL}\n\n&|" "${BBRV3_SYSCTL_SOURCE}"
        log "BBRv3: tcp_min_rcvbuf declaration restored ✅"
    fi
fi

gki_defconfig_enable CONFIG_TCP_CONG_ADVANCED CONFIG_TCP_CONG_BBR3 CONFIG_DEFAULT_BBR3

cd "${KERNEL_SRC}"
if [ "${KERNEL_VERSION}" = "5.10" ]; then
    SYSCTL_PATCH=$(fetch "${BBRV3_PATCHES_BASE}/sysctl_add_proc_dou8vec_minmax.patch") \
        || warn "BBRv3: couldn't download the sysctl proc_dou8vec_minmax patch — continuing without it"
    if [ -n "$SYSCTL_PATCH" ]; then
        if ! grep -qF 'int proc_dou8vec_minmax(' "${KERNEL_SRC}/include/linux/sysctl.h" 2>/dev/null; then
            echo "$SYSCTL_PATCH" | patch -p1 --forward --no-backup-if-mismatch \
                || warn "BBRv3: sysctl proc_dou8vec_minmax patch did not apply cleanly — continuing"
            SYSCTL_FIX=$(fetch "${BBRV3_PATCHES_BASE}/sysctl_fix_data-races_in_proc_dou8vec_minmax.patch") \
                || warn "BBRv3: couldn't download the sysctl data-races fix — continuing without it"
            if [ -n "$SYSCTL_FIX" ]; then
                echo "$SYSCTL_FIX" | patch -p1 --forward --no-backup-if-mismatch \
                    || warn "BBRv3: sysctl data-races fix did not apply cleanly — continuing"
            fi
        fi
    fi
fi

python3 "${ROOT_DIR}/kernel/patches/bbrv3/enforcer.py" "${KERNEL_SRC}/net/ipv4/tcp_cong.c" \
    || error "BBRv3: enforcer injection into tcp_cong.c failed!"

cd "${ROOT_DIR}"

log "BBRv3 patch applied, default-congestion enforcer injected ✅"
