#!/usr/bin/env bash

# ======================================================
# 📱 REGISTRY — Device
# ======================================================
# Device layer on top of pure GKI: active device comes from "device" in kernel/features.json,
# its patches and supported kernel versions from device/<name>/device.json

run_device() {
    local device manifest feature script
    local -a features
    device="$(jq -r '.device // empty' "$FEATURES_FILE")"
    [ -n "$device" ] || return 0

    manifest="${ROOT_DIR}/device/${device}/device.json"
    [ -f "$manifest" ] || error "Device '${device}' is set in kernel/features.json but ${manifest} doesn't exist."

    echo "::group::📱 Device (${device})"
    export DEVICE_NAME="$device"
    mapfile -t features < <(jq -r '.patches | keys_unsorted[]' "$manifest")
    for feature in "${features[@]}"; do
        if ! jq -e --arg feature "$feature" --arg version "$KERNEL_VERSION" \
                '(.patches[$feature].versions // []) | index($version) != null' "$manifest" > /dev/null; then
            warn "Device patch '${feature}' isn't available for kernel ${KERNEL_VERSION} — skipping."
            SKIPPED_PATCHES="${SKIPPED_PATCHES:+${SKIPPED_PATCHES},}${feature}"
            continue
        fi
        script="${ROOT_DIR}/device/${device}/patches/${feature}/${feature}.sh"
        [ -f "$script" ] || error "Device patch '${feature}' is listed in ${manifest} but ${script} doesn't exist."
        source "$script"
        APPLIED_PATCHES="${APPLIED_PATCHES:+${APPLIED_PATCHES},}${feature}"
    done
    echo "::endgroup::"
}
