"""Copy chat assets into a Qrisp checkout without replacing existing files."""

import argparse
from pathlib import Path
import sys

ASSET_PATHS = (
    "css/chat.css",
    "js/chat.js",
    "js/vendor/marked.umd.js",
    "js/vendor/purify.min.js",
    "js/vendor/marked-LICENSE.txt",
    "js/vendor/DOMPurify-LICENSE-APACHE.txt",
    "js/vendor/DOMPurify-LICENSE-MPL.txt",
    "js/vendor/THIRD_PARTY_NOTICES.md",
)


def check_parents(root: Path, relative: Path) -> None:
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"Refusing symlink destination directory: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"Destination directory is blocked by a file: {current}")


def destination_state(root: Path, relative: Path, content: bytes) -> str:
    check_parents(root, relative)
    target = root / relative
    if target.is_symlink():
        raise ValueError(f"Refusing symlink destination: {target}")
    if not target.exists():
        return "copy"
    if not target.is_file() or target.read_bytes() != content:
        raise ValueError(f"Existing destination differs from packaged asset: {target}")
    return "identical"


def install(qrisp_root: Path, *, dry_run: bool = False) -> None:
    root = qrisp_root.expanduser().resolve()
    conf_relative = Path("documentation/source/conf.py")
    check_parents(root, conf_relative)
    conf = root / conf_relative
    if conf.is_symlink() or not conf.is_file():
        raise ValueError(f"Expected a Qrisp checkout with a regular file at {conf}")

    packaged = Path(__file__).resolve().parent / "_static"
    plan = []
    conflicts = []
    for name in ASSET_PATHS:
        source = packaged / name
        check_parents(packaged, Path(name))
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Packaged asset is missing or not a regular file: {source}")
        content = source.read_bytes()
        relative = Path("documentation/source/_static") / name
        try:
            state = destination_state(root, relative, content)
        except ValueError as exc:
            conflicts.append(str(exc))
        else:
            plan.append((relative, content, state))

    # Preflight the complete set before creating any destination directories.
    if conflicts:
        raise ValueError("No files copied. Resolve conflicts manually:\n" + "\n".join(conflicts))

    for relative, content, state in plan:
        target = root / relative
        if state == "identical":
            print(f"Unchanged: {relative}")
        elif dry_run:
            print(f"Would copy: {relative}")
        else:
            # Check again and use exclusive creation to avoid overwriting a file
            # created after preflight. This is not a multi-file transaction.
            current_state = destination_state(root, relative, content)
            if current_state == "identical":
                print(f"Unchanged: {relative}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)
            print(f"Copied: {relative}")

    print("Dry run complete; no files changed." if dry_run else "Assets installed.")
    print("conf.py was not changed. Follow frontend/README.md for Sphinx registration.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qrisp_root", type=Path, help="Path to the target Qrisp checkout")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show the plan without writing")
    args = parser.parse_args()
    try:
        install(args.qrisp_root, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
