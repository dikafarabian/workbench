#!/usr/bin/env bash

# ======================================================
# 📦 ADDON — Droidspaces (container namespace and cgroup support)
# Repo: https://github.com/ravindu644/Droidspaces-OSS
# Config list follows the GKI guide of the latest upstream release tag.
# kABI patches stay as committed in kernel/kabi, drift is reported only.
# ======================================================

DROIDSPACES_REPO="https://github.com/ravindu644/Droidspaces-OSS"
DROIDSPACES_GUIDE="Documentation/Kernel-Configuration.md"
DROIDSPACES_KABI_DIR="Documentation/resources/kernel-patches/GKI"
DROIDSPACES_BLOCKED_CONFIGS=" CONFIG_CFS_BANDWIDTH CONFIG_CGROUP_PIDS CONFIG_NF_TABLES "
GKI_DEFCONFIG="${KERNEL_SRC}/arch/arm64/configs/gki_defconfig"

DROIDSPACES_CONFIGS=(
    CONFIG_SYSVIPC
    CONFIG_POSIX_MQUEUE
    CONFIG_PID_NS
    CONFIG_IPC_NS
    CONFIG_UTS_NS
    CONFIG_DEVTMPFS
    CONFIG_CGROUP_DEVICE
    CONFIG_NET_NS
    CONFIG_NETFILTER_XT_TARGET_LOG
    CONFIG_NETFILTER_XT_MATCH_RECENT
    CONFIG_NETFILTER_XT_MATCH_ADDRTYPE
    CONFIG_BINFMT_ELF
    CONFIG_BINFMT_SCRIPT
    CONFIG_USER_NS
    CONFIG_MACVLAN
    CONFIG_IP6_NF_NAT
    CONFIG_IP6_NF_TARGET_MASQUERADE
    CONFIG_IP_NF_TARGET_REJECT
    CONFIG_IP6_NF_TARGET_REJECT
    CONFIG_IP_SET
    CONFIG_IP_SET_HASH_IP
    CONFIG_IP_SET_HASH_NET
    CONFIG_NETFILTER_XT_SET
    CONFIG_TMPFS_POSIX_ACL
    CONFIG_TMPFS_XATTR
)

droidspaces_fetch_upstream() {
    local dir="$1" tag
    tag="$(git ls-remote --tags --refs --sort=-v:refname "$DROIDSPACES_REPO" | sed -n '1s#.*refs/tags/##p')"
    [ -n "$tag" ] || return 1
    retry 3 run_quiet git clone --depth 1 --branch "$tag" --filter=blob:none --sparse "$DROIDSPACES_REPO" "$dir" || return 1
    git -C "$dir" sparse-checkout set "$DROIDSPACES_KABI_DIR" || return 1
    echo "$tag"
}

droidspaces_guide_configs() {
    awk '/^## GKI kernels/{g=1;next} g&&/^### Step 2/{s=1;next} s&&/^### Step 3/{exit} s&&/^```makefile/{b=1;next} b&&/^```/{exit} b&&/^CONFIG_[A-Za-z0-9_]+=y$/{sub(/=y$/,"");print}' "$1"
}

droidspaces_patch_changes() {
    grep -E '^[+-]' "$1" | grep -vE '^(\+\+\+|---)'
}

droidspaces_report_kabi_drift() {
    local upstream_dir="$1" tag="$2" name upstream_patch
    while read -r name; do
        case "$name" in
            sysvipc_below_6_12) upstream_patch="below-kernel-6.12/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch" ;;
            posix_mqueue_5_10) upstream_patch="below-kernel-6.12/002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch" ;;
            sysvipc_6_12) upstream_patch="kernel-6.12/001.GKI-6.12-or-above-fix_sysvipc_kabi.patch" ;;
            *) continue ;;
        esac
        if [ ! -f "${upstream_dir}/${DROIDSPACES_KABI_DIR}/${upstream_patch}" ]; then
            warn "Droidspaces ${tag}: upstream kABI patch for ${name} not found (${upstream_patch})"
        elif ! diff -q <(droidspaces_patch_changes "${ROOT_DIR}/kernel/kabi/${name}.patch") \
                <(droidspaces_patch_changes "${upstream_dir}/${DROIDSPACES_KABI_DIR}/${upstream_patch}") > /dev/null; then
            warn "Droidspaces ${tag}: kABI patch ${name} differs from upstream — review and boot-test before updating kernel/kabi/${name}.patch"
        fi
    done < <(jq -r --arg version "$KERNEL_VERSION" '.versions[$version].kabi[]' "$FEATURES_FILE")
}

log "Enabling Droidspaces support..."

DROIDSPACES_WORK="$(mktemp -d)"
if DROIDSPACES_VERSION="$(droidspaces_fetch_upstream "${DROIDSPACES_WORK}/upstream")"; then
    mapfile -t GUIDE_CONFIGS < <(droidspaces_guide_configs "${DROIDSPACES_WORK}/upstream/${DROIDSPACES_GUIDE}")
    if [ "${#GUIDE_CONFIGS[@]}" -ge 10 ]; then
        NEW_GUIDE_CONFIGS=()
        for cfg in "${GUIDE_CONFIGS[@]}"; do
            if [[ "$DROIDSPACES_BLOCKED_CONFIGS" == *" ${cfg} "* ]]; then
                warn "Droidspaces ${DROIDSPACES_VERSION}: guide lists ${cfg}, blocked (breaks kABI) — skipping"
            elif [[ " ${DROIDSPACES_CONFIGS[*]} " != *" ${cfg} "* ]]; then
                DROIDSPACES_CONFIGS+=("$cfg")
                NEW_GUIDE_CONFIGS+=("$cfg")
            fi
        done
        if [ "${#NEW_GUIDE_CONFIGS[@]}" -gt 0 ]; then
            log "Droidspaces ${DROIDSPACES_VERSION}: guide adds ${#NEW_GUIDE_CONFIGS[@]} option(s) beyond the committed list: ${NEW_GUIDE_CONFIGS[*]}"
        fi
    else
        warn "Droidspaces ${DROIDSPACES_VERSION}: guide config list not found — using the committed list"
    fi
    droidspaces_report_kabi_drift "${DROIDSPACES_WORK}/upstream" "$DROIDSPACES_VERSION"
else
    DROIDSPACES_VERSION=""
    warn "Droidspaces: upstream fetch failed — using the committed list"
fi
rm -rf "$DROIDSPACES_WORK"

MISSING_CONFIGS=()
for cfg in "${DROIDSPACES_CONFIGS[@]}"; do
    grep -q "^${cfg}=y" "$GKI_DEFCONFIG" || MISSING_CONFIGS+=("${cfg}=y")
done
if [ "${#MISSING_CONFIGS[@]}" -gt 0 ]; then
    for cfg in "${DROIDSPACES_CONFIGS[@]}"; do
        sed -i "/^# ${cfg} is not set$/d" "$GKI_DEFCONFIG"
    done
    {
        echo ""
        echo "# Droidspaces — added by addon (missing from base defconfig)"
        printf '%s\n' "${MISSING_CONFIGS[@]}"
    } >> "$GKI_DEFCONFIG"
    log "Droidspaces: added ${#MISSING_CONFIGS[@]} missing config(s): ${MISSING_CONFIGS[*]}"
else
    log "Droidspaces: all required configs already present"
fi
log "Droidspaces configs enabled ✅"

if [ -n "$DROIDSPACES_VERSION" ]; then
    log "Droidspaces version: ${DROIDSPACES_VERSION}"
fi
