"""Bootstrapping commands for the group collaboration software assignment.

This starter implements identity/configuration and *local* status only.
Human-to-agent commands SYNC/PUB/INT/REV/TEST/STATUS/FINAL are specified
in specs/04_command_reference.md and specs/05_command_procedures.md and
will be implemented in subsequent milestones. The local `status` is not
represented as a complete agent-level STATUS procedure.
"""

from __future__ import annotations

import argparse
import secrets
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


def cmd_sync(args: argparse.Namespace) -> int:
    """Safe, read-only discovery phase of the agent-level SYNC procedure.

    This intentionally does NOT automatically merge/rebase or claim full SYNC.
    """
    root = repository_root()
    config = load_json(root / ".group" / "group.json")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root)
    if branch.returncode:
        raise GroupError("Switch to a named working branch before syncing.")
    remote = git("remote", "get-url", "origin", cwd=root)
    if remote.returncode:
        raise GroupError("Missing origin remote. Connect your GitHub repository first.")
    before = git("status", "--porcelain=v1", cwd=root)
    if before.returncode:
        raise GroupError(before.stderr.strip() or "Cannot inspect working tree")
    print(f"Working branch: {branch.stdout.strip()}")
    print(f"Uncommitted files: {len(before.stdout.splitlines())}")
    fetched = git("fetch", "origin", "--prune", "--tags", cwd=root)
    if fetched.returncode:
        raise GroupError(f"Fetch failed: {fetched.stderr.strip()}")
    canonical = str(config.get("canonical_branch", "main"))
    upstream = f"refs/remotes/origin/{canonical}"
    compare = git("rev-list", "--left-right", "--count", f"HEAD...{upstream}", cwd=root)
    if compare.returncode:
        raise GroupError(f"Cannot compare with {upstream}: {compare.stderr.strip()}")
    ahead, behind = map(int, compare.stdout.split())
    print(f"Relative to origin/{canonical}: {ahead} ahead, {behind} behind")
    refs = git("for-each-ref", "--format=%(refname)", "refs/remotes/origin", cwd=root)
    event_ids = {}
    for ref in refs.stdout.splitlines():
        if ref.endswith("/HEAD"):
            continue
        paths = git("ls-tree", "-r", "--name-only", ref, "--", ".group/events", cwd=root)
        if paths.returncode:
            continue
        for path in paths.stdout.splitlines():
            if not path.endswith(".json"):
                continue
            result = git("show", f"{ref}:{path}", cwd=root)
            if result.returncode:
                continue
            try:
                event = json.loads(result.stdout)
            except ValueError:
                print(f"WARNING: invalid JSON in {ref}:{path}")
                continue
            if not isinstance(event, dict) or event.get("group_id") != config.get("group_id"):
                print(f"WARNING: invalid group event in {ref}:{path}")
                continue
            event_ids.setdefault(event.get("event_id", path), event)
    print(f"Discoverable events across remote branches: {len(event_ids)}")
    for event in sorted(event_ids.values(), key=lambda e: e.get("created_at", "")):
        print(f"  {event.get('event_id', '?')} | {event.get('event_type', '?')} | {event.get('person_id', '?')} | {event.get('summary', '')}")
    print("Discovery only: no merges, rebases, commits, or event publication performed.")
    print("Full agent SYNC still requires tracking new events, considering relevance, safe canonical update, and validation.")
    return 0



def cmd_pub(args: argparse.Namespace) -> int:
    """Publish a reviewed, already-staged contribution and a durable event.

    This is a guarded mechanical helper for the agent's PUB procedure, not
    a substitute for human/agent review of the actual code and test meaning.
    """
    root = repository_root()
    group = root / ".group"
    config = load_json(group / "group.json")
    identity = load_json(group / "local" / "identity.json")
    person_id = identity.get("person_id")
    validate_ids(config.get("group_id"), person_id)
    current = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root)
    if current.returncode:
        raise GroupError("PUB requires a named personal work branch.")
    branch = current.stdout.strip()
    if not branch.startswith(f"people/{person_id}/"):
        raise GroupError(f"PUB requires a branch starting with people/{person_id}/ (currently {branch}).")
    remote = git("remote", "get-url", "origin", cwd=root)
    if remote.returncode:
        raise GroupError("Configure the origin remote before PUB.")
    if not args.summary.strip():
        raise GroupError("Provide a non-empty --summary.")
    if not args.tests_run:
        raise GroupError("Report actual validation using --tests-run, even if checks were unavailable.")
    if args.tests_run.strip().lower() in ("passed", "all passed", "ok"):
        raise GroupError("--tests-run must name the actual command or concrete check performed.")
    staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMRT", cwd=root)
    if staged.returncode:
        raise GroupError("Unable to inspect staged changes.")
    files = [x for x in staged.stdout.splitlines() if x]
    if not files:
        raise GroupError("No staged files. Review changes, then run git add <files> before PUB.")
    status = git("status", "--porcelain=v1", "--untracked-files=all", cwd=root)
    if status.returncode:
        raise GroupError("Cannot inspect working tree.")
    # Refuse ambiguous mixed snapshots: no unstaged changes or untracked files.
    if git("diff", "--quiet", cwd=root).returncode != 0 or any(x.startswith("??") for x in status.stdout.splitlines()):
        raise GroupError("Unstaged/untracked files remain. Stage or discard them after review before PUB.")
    forbidden = (".env", ".pem", ".key", "id_rsa", "credentials", "token", "secret", ".group/local/")
    suspect = [f for f in files if any(marker in f.lower() for marker in forbidden)]
    if suspect:
        raise GroupError("Possible sensitive/local files staged; inspect and unstage: " + ", ".join(suspect))
    if any(x.startswith(".group/events/") for x in files):
        raise GroupError("PUB must not stage existing event files with the code change.")
    if git("diff", "--cached", "--check", cwd=root).returncode:
        raise GroupError("Staged changes fail git diff --check; fix before PUB.")
    # A second explicit guard prevents publishing without the human/agent having
    # run and judged suitable checks first.
    if not args.checked:
        print("Staged files:")
        for f in files:
            print("  " + f)
        print("Review the actual diff and run the checks named in --tests-run first.")
        print("Then rerun the same command with --checked (confirmation of prior review).")
        return 0
    # Commit content before producing the event, so its commit pin is exact.
    made = git("commit", "-m", f"Publish: {args.summary.strip()}", cwd=root)
    if made.returncode:
        raise GroupError("Code commit failed: " + made.stderr.strip())
    commit = git("rev-parse", "HEAD", cwd=root).stdout.strip()
    pushed = git("push", "-u", "origin", branch, cwd=root)
    if pushed.returncode:
        raise GroupError("Code committed locally but PUSH FAILED; do not claim PUB completed. " + pushed.stderr.strip())

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(4)
    change_id = "C-" + stamp + "-" + person_id + "-" + suffix
    event_id = "E-" + stamp + "-" + person_id + "-" + suffix
    event_path = group / "events" / f"{event_id}.json"
    event = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": event_id,
        "event_type": "change_published",
        "group_id": config["group_id"],
        "person_id": person_id,
        "created_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "related_events": [],
        "change_id": change_id,
        "branch": branch,
        "commit": commit,
        "summary": args.summary.strip(),
        "files_changed": files,
        "interface_changes": args.interface_change or [],
        "tests_run": [args.tests_run],
        "known_issues": args.known_issue or [],
        "proposed_for_integration": not args.not_for_integration,
    }
    write_json_new(event_path, event)
    stage_event = git("add", "--", str(event_path.relative_to(root)), cwd=root)
    if stage_event.returncode:
        raise GroupError("Code pushed, but event staging failed: " + stage_event.stderr.strip())
    event_commit = git("commit", "-m", f"Publish event {change_id}", cwd=root)
    if event_commit.returncode:
        raise GroupError("Code pushed, but event commit failed: " + event_commit.stderr.strip())
    event_push = git("push", "origin", branch, cwd=root)
    if event_push.returncode:
        raise GroupError("Event committed locally, but PUSH FAILED; publication incomplete: " + event_push.stderr.strip())
    print(f"Published {change_id}")
    print(f"Code commit: {commit}")
    print(f"Event: {event_path.relative_to(root)}")
    print("GitHub branch: " + branch)
    print("PUB mechanical publication complete. Review/test claims are supplied by the operator, not independently verified by this helper.")
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
    sync = subs.add_parser("sync", help="Fetch and inspect group state (safe discovery phase only)")
    sync.set_defaults(handler=cmd_sync)
    pub = subs.add_parser("pub", help="Publish staged code and immutable change_published event (guarded helper)")
    pub.add_argument("--summary", required=True)
    pub.add_argument("--tests-run", required=True, help="Exact command/check actually performed")
    pub.add_argument("--interface-change", action="append", default=[])
    pub.add_argument("--known-issue", action="append", default=[])
    pub.add_argument("--not-for-integration", action="store_true")
    pub.add_argument("--checked", action="store_true", help="Confirm manual review and checks completed")
    pub.set_defaults(handler=cmd_pub)
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
