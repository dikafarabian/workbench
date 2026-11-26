#!/usr/bin/env bash

# ======================================================
# 🚦 KMI — Registry
# ======================================================
# KMI_REFERENCE names a directory under kernel/kmi/ref/ built from the stock ROM.
# Empty disables the gate. When set, the module version bypass is not applied.

run_kmi_gate() {
    [ -n "${KMI_REFERENCE:-}" ] || return 0

    local reference_dir="${ROOT_DIR}/kernel/kmi/ref/${KMI_REFERENCE}"
    local image="${OUT_DIR}/arch/${ARCH}/boot/Image"
    local report="${OUT_DIR}/kmi_report.json"

    [ -f "${reference_dir}/meta.json" ] \
        || error "KMI reference not found: kernel/kmi/ref/${KMI_REFERENCE}"

    if [ "${BUILD_SYSTEM}" = "KLEAF" ]; then
        warn "KMI gate supports Make builds only — skipped"
        return 0
    fi

    if [ "${DRY_RUN:-false}" = "true" ]; then
        log "KMI gate skipped (dry run)"
        return 0
    fi

    echo "::group::🚦 KMI Gate (${KMI_REFERENCE})"
    if ! python3 "${ROOT_DIR}/kernel/kmi/gate.py" --reference "$reference_dir" --image "$image" --report "$report" --limit 40; then
        echo "::endgroup::"
        mkdir -p "${ROOT_DIR}/debug-stage"
        cp "$report" "${ROOT_DIR}/debug-stage/kmi-report-${KERNEL_VARIANT,,}.json" 2> /dev/null || true
        error "KMI gate failed — the kernel does not keep the stock KMI (report: ${report})"
    fi
    echo "::endgroup::"
}
