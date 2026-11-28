#!/usr/bin/env bash

# ======================================================
# 🔑 ROOT SOLUTION — Shared Steps
# ======================================================
# Steps every variant in variants/ runs: preseed, setup, version, configs

source "${ROOT_DIR}/kernel/ksu/checkpoint/mirrors.sh"

ksu_preseed() {
    local key="$1" ref_var="${1^^}_REF" candidate_var="CANDIDATE_${1^^}"
    mirror_preseed "$key" "$KSU_DIR" "${!ref_var:-}" "${!candidate_var:-false}" "$(mirror_label)" || true
}

ksu_patcher() {
    python3 "${ROOT_DIR}/kernel/ksu/variants/${KERNEL_VARIANT,,}/$1" "${@:2}"
}

ksu_integrate() {
    local name="$1" setup_url="$2" setup_ref="$3" preseed_key="${4:-}"
    log "Integrating ${name}..."
    cd "$KERNEL_SRC"
    [ -z "$preseed_key" ] || ksu_preseed "$preseed_key"
    run_upstream_setup "$name" "$setup_url" "$setup_ref"
    [ -d "$KSU_DIR" ] || error "${name}: $(basename "$KSU_DIR") dir not found after setup!"
    verify_pinned_ref "$name" "$KSU_DIR" "$setup_ref"
    cd "$ROOT_DIR"
    log "${name} integrated ✅"
}

ksu_git_version() {
    local default_tag="$1" offset="${2:-0}" rev="${3:-HEAD}" count
    count=$(git -C "$KSU_DIR" rev-list --count "$rev" 2>/dev/null || echo 0)
    KSU_VERSION_CODE=$((30000 + count + offset))
    KSU_TAG_NAME=$(git -C "$KSU_DIR" describe --tags --abbrev=0 "$rev" 2>/dev/null || echo "$default_tag")
}

ksu_publish_version() {
    KSU_UAPI_VERSION="$(ksu_uapi_version "$KSU_DIR")"
    VARIANT_VERSION_DISPLAY="$(format_ksu_version "$KSU_TAG_NAME" "$KSU_VERSION_CODE" "$KSU_UAPI_VERSION")"
    log "Version: ${VARIANT_VERSION_DISPLAY}"
}

ksu_apply_pinned_commit() {
    local key="$1" offset="$2" label="$3" ref_var="${1^^}_REF" candidate_var="CANDIDATE_${1^^}"
    local ref="${!ref_var:-}" suffix="" patch_file mirror_url
    [ -n "$ref" ] || error "${label}: no ${key} ref resolved!"
    [ "$offset" -eq 0 ] || suffix="~${offset}"
    patch_file="$(mktemp)"
    mirror_url="$(mirror_clone_url "$key" 2>/dev/null || true)"
    if [ "${!candidate_var:-false}" != "true" ] && [ -n "$mirror_url" ] \
        && fetch -o "$patch_file" "${mirror_url%.git}/commit/${ref}${suffix}.patch" 2>/dev/null \
        && [ -s "$patch_file" ]; then
        log "${label}: ${ref:0:12}${suffix} from mirror"
    else
        fetch -o "$patch_file" "$(mirror_source_url "$key" | sed 's/\.git$//')/commit/${ref}${suffix}.patch" \
            || error "${label}: failed to download ${ref:0:12}${suffix}!"
        log "${label}: ${ref:0:12}${suffix} from upstream"
    fi
    apply_patch "$label" "$patch_file" "$KSU_DIR" --fuzz=3
    rm -f "$patch_file"
}

ksu_enable_configs() {
    log "Enabling KSU configs..."
    gki_defconfig_enable "$@"
    log "Configs enabled ✅"
}
