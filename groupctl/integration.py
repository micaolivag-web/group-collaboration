
import json
import subprocess


def read_event(branch: str, event_path: str) -> dict:
    """Read a collaboration event from a Git branch."""

    result = subprocess.run(
        ["git", "--no-pager", "show", f"{branch}:{event_path}"],
        capture_output=True,
        text=True,
        check=True
    )

    event = json.loads(result.stdout)

    if not isinstance(event, dict):
        raise ValueError("Expected a JSON object")

    return event

def find_published_change(branch: str, change_id: str) -> dict:
    """Find a published change by its change ID."""

    result = subprocess.run(
        [
            "git", "ls-tree", "-r", "--name-only",
            branch, "--", ".group/events/"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    for event_path in result.stdout.splitlines():
        if not event_path.endswith(".json"):
            continue

        event = read_event(branch, event_path)

        if (
            event.get("event_type") == "change_published"
            and event.get("change_id") == change_id
        ):
            return event

    raise ValueError(f"Published change not found: {change_id}")

def validate_published_commit(event: dict) -> str:
    """Verify that a published commit exists in its Git branch."""

    branch = event.get("branch")
    commit = event.get("commit")

    if not branch or not commit:
        raise ValueError("Missing branch or commit")

    # Check that the commit exists
    result = subprocess.run(
        ["git", "cat-file", "-t", commit],
        capture_output=True,
        text=True
    )

    if result.returncode != 0 or result.stdout.strip() != "commit":
        raise ValueError("Invalid or missing commit")

    # Check that the commit belongs to the published branch
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor",
         commit, f"origin/{branch}"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise ValueError("Commit not found in published branch")

    return commit

def inspect_published_diff(event: dict) -> str:
    """Inspect the actual code changes in a published commit."""

    commit = validate_published_commit(event)

    result = subprocess.run(
        ["git", "--no-pager", "show", "--format=", commit],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout



def check_integration_target() -> str:
    """Check that the current branch is safe for integration."""

    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True
    )

    branch = branch_result.stdout.strip()

    if not branch.startswith("people/"):
        raise ValueError("INT must run on a personal branch")

    status_result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        capture_output=True,
        text=True,
        check=True
    )

    if status_result.stdout.strip():
        raise ValueError(
            "Uncommitted changes detected. Save your work before INT."
        )

    return branch
