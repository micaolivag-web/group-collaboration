"""Bootstrapping commands for the group collaboration software assignment.

This starter implements identity/configuration and *local* status only.
Human-to-agent commands SYNC/PUB/INT/REV/TEST/STATUS/FINAL are specified
in specs/04_command_reference.md and specs/05_command_procedures.md and
will be implemented in subsequent milestones. The local `status` is not
represented as a complete agent-level STATUS procedure.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

PROTOCOL_VERSION = "0.1"
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*$")


class GroupError(Exception):
    """Expected, recoverable user error."""


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)


def repository_root() -> Path:
    result = git("rev-parse", "--show-toplevel")
    if result.returncode:
        raise GroupError("Not inside a Git repository. Run 'git init -b main' first.")
    return Path(result.stdout.strip()).resolve()


def write_json_new(path: Path, payload: dict) -> None:
    """Never silently overwrite committed configuration or member identity."""
    if path.exists():
        raise GroupError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise GroupError(f"Missing {path}. Run 'python -m groupctl init' first.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise GroupError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GroupError(f"Expected a JSON object in {path}")
    return value


def validate_ids(group_id: str | None, person_id: str, canonical_branch: str | None = None) -> None:
    for kind, value in (("person ID", person_id), ("group ID", group_id)):
        if value is not None and not ID_RE.fullmatch(value):
            raise GroupError(f"Invalid {kind}: use letters, numbers, _ or -, beginning with a letter.")
    if canonical_branch is not None and not BRANCH_RE.fullmatch(canonical_branch):
        raise GroupError("Invalid canonical branch. Example: main")


def cmd_init(args: argparse.Namespace) -> int:
    validate_ids(args.group_id, args.person_id, args.canonical_branch)
    root = repository_root()
    group = root / ".group"
    group_file = group / "group.json"
    if group_file.exists():
        raise GroupError("Group already configured. Use 'python -m groupctl join' to register this person.")

    # Ensure that a retry cannot silently modify existing records.
    targets = [
        group / "members" / f"{args.person_id}.json",
        group / "local" / "identity.json",
    ]
    for target in targets:
        if target.exists():
            raise GroupError(f"Refusing to overwrite existing file: {target}")

    write_json_new(group_file, {
        "protocol_version": PROTOCOL_VERSION,
        "group_id": args.group_id,
        "canonical_branch": args.canonical_branch,
        "assignment_file": ".group/assignment/assignment.md",
    })
    assignment_file = group / "assignment" / "assignment.md"
    assignment_file.parent.mkdir(parents=True, exist_ok=True)
    if not assignment_file.exists():
        assignment_file.write_text(
            "# Group Assignment\n\n"
            "Implement Group Collaboration Software Version 0.1.\n\n"
            "Authoritative specification: `specs/00_group_collaboration_assignment.md` "
            "and companion files `specs/01_*.md` to `specs/07_*.md`.\n",
            encoding="utf-8",
        )
    for rel in ("events", "final", "local"):
        directory = group / rel
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").touch(exist_ok=True)
    create_member(group, args.person_id, args.name)
    print(f"Initialized group {args.group_id} on canonical branch {args.canonical_branch}.")
    print(f"Local identity: {args.person_id} ({args.name})")
    print("Next: inspect .group/, then make your initial Git commit.")
    return 0


def create_member(group: Path, person_id: str, name: str) -> None:
    write_json_new(group / "members" / f"{person_id}.json", {
        "protocol_version": PROTOCOL_VERSION,
        "person_id": person_id,
        "display_name": name,
        "joined_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })
    write_json_new(group / "local" / "identity.json", {
        "person_id": person_id,
    })


def cmd_join(args: argparse.Namespace) -> int:
    validate_ids(None, args.person_id)
    root = repository_root()
    group = root / ".group"
    config = load_json(group / "group.json")
    if config.get("protocol_version") != PROTOCOL_VERSION:
        raise GroupError("Unsupported protocol_version in group.json")
    if (group / "local" / "identity.json").exists():
        raise GroupError("This clone already has a local identity. Do not overwrite it.")
    create_member(group, args.person_id, args.name)
    print(f"Joined group {config.get('group_id')} as {args.person_id} ({args.name}).")
    print(f"Commit and push .group/members/{args.person_id}.json so teammates can recognize you.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = repository_root()
    group = root / ".group"
    config = load_json(group / "group.json")
    identity_file = group / "local" / "identity.json"
    identity = load_json(identity_file) if identity_file.is_file() else {}
    head = git("rev-parse", "--verify", "HEAD", cwd=root)
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root)
    dirty = git("status", "--porcelain=v1", "--untracked-files=all", cwd=root)
    remotes = git("remote", cwd=root)
    canonical = config.get("canonical_branch", "main")
    canonical_remote = git("rev-parse", "--verify", f"refs/remotes/origin/{canonical}", cwd=root)
    events_dir = group / "events"
    events = list(events_dir.glob("*.json")) if events_dir.is_dir() else []

    print(f"Group: {config.get('group_id', '(unknown)')}")
    print(f"Person: {identity.get('person_id', '(not set in this clone)')}")
    print(f"Local branch: {branch.stdout.strip() or '(detached/unborn)'}")
    print(f"Local commit: {head.stdout.strip() if head.returncode == 0 else '(no commits yet)'}")
    print(f"Uncommitted/untracked files: {len(dirty.stdout.splitlines())}")
    print(f"Canonical branch: {canonical}")
    print(f"Cached origin/{canonical}: {canonical_remote.stdout.strip() if canonical_remote.returncode == 0 else '(not fetched)'}")
    print(f"Remotes: {', '.join(remotes.stdout.split()) or '(none configured)'}")
    print(f"Event files in current checkout: {len(events)}")
    print("Note: this is LOCAL starter status, not the full agent STATUS procedure.")
    print("It does not yet fetch group events, compare ahead/behind, or assess blockers/tests.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="groupctl", description="Group collaboration helper (v0.1 starter)")
    subs = parser.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init", help="Create .group/ files and register the first person")
    init.add_argument("--group-id", required=True, help="e.g., G-12")
    init.add_argument("--person-id", required=True, help="e.g., P17")
    init.add_argument("--name", required=True, help="display name")
    init.add_argument("--canonical-branch", default="main")
    init.set_defaults(handler=cmd_init)
    join = subs.add_parser("join", help="Register another member in their own clone")
    join.add_argument("--person-id", required=True)
    join.add_argument("--name", required=True)
    join.set_defaults(handler=cmd_join)
    status = subs.add_parser("status", help="Print local repository/identity snapshot (starter)")
    status.set_defaults(handler=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except GroupError as exc:
        print(f"groupctl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
