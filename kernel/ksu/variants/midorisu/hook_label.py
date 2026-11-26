import pathlib
import re
import sys

LABEL = "De-inlined SUSFS"
SOURCE = "kernel/supercall/dispatch.c"
INLINE_LABEL = re.compile(
    r'(#ifdef CONFIG_KSU_SUSFS\n[ \t]*const char \*type = ")Inline(";)'
)


def main():
    source = pathlib.Path(sys.argv[1]) / SOURCE
    content = source.read_text()

    if f'"{LABEL}"' in content:
        print("Hook type label already reports de-inlined SuSFS, skipping.")
        return 0

    updated, count = INLINE_LABEL.subn(rf"\g<1>{LABEL}\g<2>", content)
    if count != 1:
        print(f"{source}: inline hook type label not found.")
        return 1

    source.write_text(updated)
    print(f"Hook type label set to {LABEL}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
