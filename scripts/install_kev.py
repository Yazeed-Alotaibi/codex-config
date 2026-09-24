#!/usr/bin/env python3
"""Install the shared Kev skill and managed instructions with Python 3.10+.

Only the marked instruction block and source-listed skill files are managed.
Other instructions and extra skill files are preserved. No network, subprocess,
package installation, authentication, or client settings changes are performed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid


BEGIN = "<!-- BEGIN CODEX-CONFIG KEV -->"
END = "<!-- END CODEX-CONFIG KEV -->"
BOM = b"\xef\xbb\xbf"
SKILL_NAME = "kev-decisions"
IGNORED_DIRS = {"__pycache__", "node_modules"}


class InstallError(Exception):
    """A preflight failure that needs user attention."""


@dataclass(frozen=True)
class Write:
    path: Path
    data: bytes
    previous: bytes | None
    mode: int


@dataclass
class Plan:
    directories: list[Path]
    writes: list[Write]
    override: Path | None


def absolute(path: str | Path) -> Path:
    # abspath normalizes '..' without silently following a managed symlink.
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def ensure_type(path: Path, *, directory: bool) -> None:
    if path.is_symlink():
        raise InstallError(f"Symlinks are not supported at managed paths: {path}")
    if path.exists():
        good = path.is_dir() if directory else path.is_file()
        if not good:
            expected = "directory" if directory else "regular file"
            raise InstallError(f"Path collision: expected a {expected}: {path}")


def validate_directory(path: Path, anchor: Path) -> None:
    """Validate the managed subtree, including any missing root's parents.

    Existing ancestors above an explicit root are not managed; this also allows
    normal OS aliases such as macOS /var. The root itself must not be a symlink.
    """
    current = path
    while True:
        ensure_type(current, directory=True)
        if current == anchor or current.parent == current:
            break
        current = current.parent
    current = anchor.parent
    while not current.exists() and current.parent != current:
        ensure_type(current, directory=True)
        current = current.parent
    if not current.is_dir():
        raise InstallError(f"Path collision: expected a directory: {current}")


def read_optional(path: Path) -> bytes | None:
    ensure_type(path, directory=False)
    return path.read_bytes() if path.exists() else None


def decode(data: bytes, path: Path) -> tuple[str, bytes]:
    try:
        return data.decode("utf-8-sig"), BOM if data.startswith(BOM) else b""
    except UnicodeDecodeError as exc:
        raise InstallError(f"Expected UTF-8 text: {path}") from exc


def block_span(text: str, path: Path, *, required: bool) -> tuple[int, int] | None:
    markers: list[tuple[str, int, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body.strip() in (BEGIN, END):
            markers.append((body.strip(), offset, offset + len(body)))
        offset += len(line)
    begin_count = text.count("BEGIN CODEX-CONFIG KEV")
    end_count = text.count("END CODEX-CONFIG KEV")
    if not markers and not begin_count and not end_count and not required:
        return None
    if (
        len(markers) != 2
        or [entry[0] for entry in markers] != [BEGIN, END]
        or begin_count != 1
        or end_count != 1
    ):
        raise InstallError(
            f"Malformed or duplicate managed markers in {path}; expected exactly "
            "one BEGIN/END pair on separate lines"
        )
    return markers[0][1], markers[1][2]


def source_block(source: Path) -> str:
    instructions = source / "AGENTS.md"
    data = read_optional(instructions)
    if data is None:
        raise InstallError(f"Missing source instructions: {instructions}")
    text, _ = decode(data, instructions)
    span = block_span(text, instructions, required=True)
    assert span is not None
    return text[span[0] : span[1]].replace("\r\n", "\n").replace("\r", "\n")


def update_instructions(previous: bytes | None, block: str, path: Path) -> bytes:
    text, bom = decode(previous or b"", path)
    span = block_span(text, path, required=False)
    match = re.search(r"\r\n|\n|\r", text)
    newline = match.group(0) if match else "\n"
    local_block = block.replace("\n", newline)
    if span is not None:
        updated = text[: span[0]] + local_block + text[span[1] :]
    elif text:
        separator = newline if text.endswith(("\r", "\n")) else newline * 2
        updated = text + separator + local_block + newline
    else:
        updated = local_block + newline
    return bom + updated.encode("utf-8")


def skill_source(source: Path) -> tuple[list[Path], list[tuple[Path, bytes, int]]]:
    root = source / "skills" / SKILL_NAME
    validate_directory(root, source)
    if not root.is_dir():
        raise InstallError(f"Missing source skill directory: {root}")
    dirs: list[Path] = [Path(".")]
    files: list[tuple[Path, bytes, int]] = []

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            if child.name.startswith(".") or child.name in IGNORED_DIRS:
                continue
            if child.name.endswith((".pyc", ".pyo")):
                continue
            if child.is_symlink():
                raise InstallError(f"Source symlink is not supported: {child}")
            if child.is_dir():
                dirs.append(child.relative_to(root))
                visit(child)
            elif child.is_file():
                data = child.read_bytes()
                decode(data, child)  # This skill is a portable UTF-8 text bundle.
                files.append((child.relative_to(root), data, stat.S_IMODE(child.stat().st_mode)))
            else:
                raise InstallError(f"Source is not a regular file or directory: {child}")

    visit(root)
    if not any(relative == Path("SKILL.md") for relative, _, _ in files):
        raise InstallError(f"Missing source SKILL.md: {root / 'SKILL.md'}")
    return dirs, files


def build_plan(source: Path, home: Path, codex: Path, claude: Path) -> Plan:
    ensure_type(source, directory=True)
    block = source_block(source)
    source_dirs, source_files = skill_source(source)
    expected_dirs: dict[Path, Path] = {}
    expected_files: dict[Path, tuple[bytes, int]] = {}

    def directory(path: Path, anchor: Path) -> None:
        validate_directory(path, anchor)
        current = path
        while True:
            expected_dirs[current] = anchor
            if current == anchor or current.parent == current:
                break
            current = current.parent
        current = anchor.parent
        while not current.exists() and current.parent != current:
            expected_dirs[current] = anchor
            current = current.parent

    def file(path: Path, data: bytes, mode: int) -> None:
        if path == source or source in path.parents:
            # An existing checkout may itself be CODEX_HOME. Its AGENTS.md is
            # already the source of this block, so accept that exact no-op.
            # The user's active global override remains an explicit managed
            # destination there. Skill copies and all other overlaps stay barred.
            shared_codex_instruction = codex == source and (
                (path == source / "AGENTS.md" and read_optional(path) == data)
                or path == source / "AGENTS.override.md"
            )
            if not shared_codex_instruction:
                raise InstallError(f"Destination overlaps the source tree: {path}")
        if path in expected_files and expected_files[path][0] != data:
            raise InstallError(f"Conflicting destinations: {path}")
        ensure_type(path, directory=False)
        expected_files[path] = (data, mode)

    for root, anchor in (
        (home / ".agents" / "skills" / SKILL_NAME, home),
        (claude / "skills" / SKILL_NAME, claude),
    ):
        for relative in source_dirs:
            directory(root / relative, anchor)
        for relative, data, mode in source_files:
            file(root / relative, data, mode)

    instruction_paths = [(codex / "AGENTS.md", codex), (claude / "CLAUDE.md", claude)]
    directory(codex, codex)
    directory(claude, claude)
    override_path = codex / "AGENTS.override.md"
    override_data = read_optional(override_path)
    override: Path | None = None
    if override_data is not None:
        override_text, _ = decode(override_data, override_path)
        block_span(override_text, override_path, required=False)
        if override_text:
            override = override_path
            instruction_paths.append((override_path, codex))
    for path, anchor in instruction_paths:
        directory(path.parent, anchor)
        previous = read_optional(path)
        data = update_instructions(previous, block, path)
        mode = stat.S_IMODE(path.stat().st_mode) if previous is not None else 0o600
        file(path, data, mode)

    collisions = expected_dirs.keys() & expected_files.keys()
    if collisions:
        raise InstallError(f"File/directory destination collision: {sorted(collisions)[0]}")
    writes: list[Write] = []
    for path, (data, mode) in sorted(expected_files.items()):
        previous = read_optional(path)
        if previous != data:
            if previous is not None:
                mode = stat.S_IMODE(path.stat().st_mode)
            writes.append(Write(path, data, previous, mode))
    directories = sorted(
        (path for path in expected_dirs if not path.exists()),
        key=lambda path: (len(path.parts), str(path)),
    )
    return Plan(directories, writes, override)


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def backup(write: Write) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = write.path.with_name(f"{write.path.name}.{timestamp}.{uuid.uuid4().hex[:8]}.bak")
    # Exclusive creation also protects any pre-existing backup with this name.
    with path.open("xb") as stream:
        stream.write(write.previous if write.previous is not None else b"")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, write.mode)
    return path


def execute(plan: Plan) -> None:
    # Recheck snapshots before the first write, so an intervening edit is not lost.
    for write in plan.writes:
        if read_optional(write.path) != write.previous:
            raise InstallError(f"File changed during preflight; rerun the installer: {write.path}")
    for directory in plan.directories:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for write in plan.writes:
        # Recheck each destination immediately before backing up/replacing it too.
        if read_optional(write.path) != write.previous:
            raise InstallError(f"File changed during installation; rerun the installer: {write.path}")
        if write.previous is not None:
            print(f"Backup: {backup(write)}")
        atomic_write(write.path, write.data, write.mode)
        print(f"Installed: {write.path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root containing AGENTS.md and skills/kev-decisions")
    parser.add_argument("--home", type=Path,
                        help="target user home; ignores CODEX_HOME and CLAUDE_CONFIG_DIR")
    parser.add_argument("--codex-home", type=Path, help="explicit Codex configuration directory")
    parser.add_argument("--claude-home", type=Path, help="explicit Claude configuration directory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="check installed content without writing")
    modes.add_argument("--dry-run", action="store_true", help="preflight and print planned paths without writing")
    args = parser.parse_args(argv)
    home = absolute(args.home if args.home is not None else Path.home())
    codex_default = home / ".codex"
    claude_default = home / ".claude"
    if args.home is None:
        codex_default = Path(os.environ.get("CODEX_HOME") or codex_default)
        claude_default = Path(os.environ.get("CLAUDE_CONFIG_DIR") or claude_default)
    codex = absolute(args.codex_home if args.codex_home is not None else codex_default)
    claude = absolute(args.claude_home if args.claude_home is not None else claude_default)
    try:
        plan = build_plan(absolute(args.source), home, codex, claude)
        if plan.override is not None:
            print(f"Active Codex instruction override also managed: {plan.override}")
        if args.check:
            for path in plan.directories:
                print(f"Missing directory: {path}")
            for write in plan.writes:
                print(f"Missing or changed: {write.path}")
            if plan.directories or plan.writes:
                return 1
            print("Kev installation is up to date.")
            return 0
        if args.dry_run:
            for path in plan.directories:
                print(f"Would create directory: {path}")
            for write in plan.writes:
                if write.previous is not None:
                    print(f"Would back up: {write.path}")
                print(f"Would install: {write.path}")
        else:
            execute(plan)
        if not plan.directories and not plan.writes:
            print("No changes needed; Kev installation is up to date.")
        return 0
    except (InstallError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
