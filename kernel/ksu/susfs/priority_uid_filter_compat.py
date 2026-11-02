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


def patch_sources(source_dir):
    wrapped = 0
    for source in source_dir.rglob("*.c"):
        content = source.read_text(errors="ignore")
        updated, parse_count = PARSE_CALL.subn(wrap, content)
        updated, case_count = SET_CASE.subn(wrap, updated)
        if parse_count or case_count:
            source.write_text(updated)
            wrapped += parse_count + case_count
    return wrapped


def main():
    ksu_dir = pathlib.Path(sys.argv[1])
    susfs_header = pathlib.Path(sys.argv[2])
    kconfig = ksu_dir / "kernel" / "Kconfig"

    if GUARD not in susfs_header.read_text(errors="ignore"):
        print("SuSFS header has no priority uid filter gate, skipping.")
        sys.exit(0)
    if KCONFIG_SYMBOL in kconfig.read_text():
        print("KernelSU source already defines the priority uid filter gate, skipping.")
        sys.exit(0)

    patch_kconfig(kconfig)
    wrapped = patch_sources(ksu_dir / "kernel")
    if not wrapped:
        print("No priority uid filter call sites found to gate.")
        sys.exit(1)
    print(f"Priority uid filter gate added, {wrapped} call site(s) wrapped.")


if __name__ == "__main__":
    main()
