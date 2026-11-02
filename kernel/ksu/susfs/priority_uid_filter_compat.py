import pathlib
import re
import sys

GUARD = "CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER"
KCONFIG_SYMBOL = "config KSU_SUSFS_PRIORITY_UID_FILTER"
KCONFIG_ANCHOR = "config KSU_SUSFS_SUS_MAP"

KCONFIG_BLOCK = (
    "config KSU_SUSFS_PRIORITY_UID_FILTER\n"
    "\tbool \"Enable to allow adding user-defined uids that will be hidden from "
    "getpriority/setpriority/ioprio_get/ioprio_set syscall\"\n"
    "\tdepends on KSU_SUSFS\n"
    "\tdefault y\n"
    "\thelp\n"
    "\t  - Allow hiding user-defined uids from syscalls like "
    "getpriority/setpriority/ioprio_get/ioprio_set.\n"
    "\t  - Effective on all processes with uid >= 10000.\n"
    "\n"
)

OPEN = f"#ifdef {GUARD}\n"
CLOSE = f"#endif // #ifdef {GUARD}\n"

HELPERS = re.compile(
    r"/\*\n \* Switches the selinux domain of the current process.*?"
    r"static void susfs_restore_creds\(struct cred \*orig_cred\) \{.*?\n\}\n",
    re.DOTALL,
)
PARSE_CALL = re.compile(
    r"^[ \t]*susfs_parse_priority_app_strings\(\);[ \t]*\n", re.MULTILINE
)
SET_CASE = re.compile(
    r"^[ \t]*case CMD_SUSFS_SET_PRIORITY_UID_FILTER:[ \t]*\n"
    r"[ \t]*susfs_set_priority_uid_filter\(arg\);[ \t]*\n"
    r"[ \t]*return 0;[ \t]*\n",
    re.MULTILINE,
)


def wrap(match):
    return OPEN + match.group(0) + CLOSE


def patch_kconfig(kconfig):
    content = kconfig.read_text()
    anchor = content.find(KCONFIG_ANCHOR)
    if anchor < 0:
        print(f"{kconfig}: {KCONFIG_ANCHOR} not found.")
        sys.exit(1)
    menu_end = re.compile(r"^endmenu\b", re.MULTILINE).search(content, anchor)
    if not menu_end:
        print(f"{kconfig}: no endmenu after {KCONFIG_ANCHOR}.")
        sys.exit(1)
    kconfig.write_text(
        content[: menu_end.start()] + KCONFIG_BLOCK + content[menu_end.start():]
    )


def gated_sources(source_dir):
    gated = {}
    for source in source_dir.rglob("*.c"):
        content = source.read_text(errors="ignore")
        updated, parse_count = PARSE_CALL.subn(wrap, content)
        updated, case_count = SET_CASE.subn(wrap, updated)
        if parse_count or case_count:
            gated[source] = updated
    return gated


def guard_unused_helpers(susfs_source):
    content = susfs_source.read_text()
    block = HELPERS.search(content)
    if not block:
        print(f"{susfs_source}: priority helpers not found, skipping.")
        return
    if content[: block.start()].endswith(OPEN):
        print("Priority helpers already gated, skipping.")
        return
    susfs_source.write_text(
        content[: block.start()] + wrap(block) + content[block.end():]
    )
    print("KernelSU source does not use the priority uid filter, helpers gated.")


def main():
    ksu_dir = pathlib.Path(sys.argv[1])
    susfs_header = pathlib.Path(sys.argv[2])
    susfs_source = pathlib.Path(sys.argv[3])
    kconfig = ksu_dir / "kernel" / "Kconfig"

    if GUARD not in susfs_header.read_text(errors="ignore"):
        print("SuSFS header has no priority uid filter gate, skipping.")
        sys.exit(0)
    if KCONFIG_SYMBOL in kconfig.read_text():
        print("KernelSU source already defines the priority uid filter gate, skipping.")
        sys.exit(0)

    gated = gated_sources(ksu_dir / "kernel")
    if not gated:
        guard_unused_helpers(susfs_source)
        sys.exit(0)

    patch_kconfig(kconfig)
    for source, updated in gated.items():
        source.write_text(updated)
    print(f"Priority uid filter gate added, {len(gated)} file(s) gated.")


if __name__ == "__main__":
    main()
