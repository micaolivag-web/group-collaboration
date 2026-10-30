# Group Collaboration Software — Step 1 Starter

This is the **first milestone** of the supplied Version 0.1 assignment, **not the completed implementation**.

This starter provides:
- a Python `groupctl` entry point;
- `init` to generate the specification-required `.group/` directories and JSON configuration;
- `join` for a second member in their *own* clone;
- `status` showing the initial local identity/Git snapshot;
- an `AGENTS.md` file describing the seven human-to-agent prompt commands;
- the eight authoritative specs under `specs/`;
- basic automated tests.

It does NOT yet implement the complete SYNC, PUB, INT, REV, TEST, STATUS or FINAL workflows, remote event exchange, or semantic validation. We will build those in later steps without changing the contract.

## Prerequisites

- Git available from the terminal (`git --version`)
- Python 3.10 or later (`python --version` or `py --version`)

## Getting started (VS Code terminal)

1. Extract the ZIP into an empty folder and open that folder in VS Code.
2. In that folder's terminal, initialize Git **only if this is a new local project**:

   ```bash
   git init -b main
   ```

3. Initialize your group's collaboration files (replace sample IDs/name with your actual values):

   ```bash
   python -m groupctl init --group-id G-12 --person-id P17 --name "Your Name"
   ```

   On Windows, if `python` is not available, use `py -m groupctl` instead.

4. See your local state:

   ```bash
   python -m groupctl status
   ```

5. Check created files:

   ```text
   .group/
   ├── group.json
   ├── assignment/assignment.md
   ├── members/P17.json
   ├── events/.gitkeep
   ├── final/.gitkeep
   └── local/.gitkeep     # local/identity.json is ignored by Git
   ```

6. Check that sensitive/local identity is excluded from version control:

   ```bash
   git status --short
   git check-ignore .group/local/identity.json
   ```

7. Make the first local commit:

   ```bash
   git add .
   git commit -m "Initialize group collaboration repository"
   ```

   If Git asks for identity, configure it with your own name and email; do not copy another student's credentials.

8. To share the project, create a new **empty GitHub repository** under your group account and add its exact URL as `origin`, then push `main`:

   ```bash
   git remote add origin YOUR_REAL_GITHUB_REPOSITORY_URL
   git push -u origin main
   ```

   Do not use placeholder URL literally. GitHub creation/push are not done by this starter.

## Work branches

After the initial repository is published, each student clones it, registers their own identity in that clone, and works on their own branch. For a new member in their own clone:

```bash
python -m groupctl join --person-id P22 --name "Teammate Name"
git switch -c people/P22/renderer
# Commit and push the new .group/members/P22.json before other members use it.
```

A person who initialized the repository can create their own branch after pushing main:

```bash
git switch -c people/P17/groupctl-core
```

Do not run `join` for the other students in the first student's clone; each clone's `.group/local/identity.json` belongs only to its owner.

## Run automated tests

```bash
python -m unittest discover -s tests -v
```

## Next milestones

2. JSON event creation/read/validation/publishing; make records immutable and uniquely named.
3. Remote SYNC and full STATUS, including discovered events and canonical comparison.
4. PUB, REV and TEST helper mechanics, controlled by the AI instructions.
5. INT with checks for Git conflicts, build/tests and semantic review.
6. FINAL proposal, human confirmation, and final canonical commit/report.
7. Three-clone GitHub demonstration, including successful and conflicting integrations.

The definitive required behavior is in `specs/`. If the starter ever disagrees with those files, the specs win.

## Milestone 2: safe SYNC discovery

Run `python -m groupctl sync` from a personal work branch after configuring `origin`.
This fetches remote refs, compares your branch with `origin/main`, and reports
structured JSON events found on remote branches. It **does not** automatically
merge or rebase. It is only the read-only discovery portion of the specification's
human-to-agent `SYNC` procedure; the AI must still reason about relevance,
previous sync state, safe canonical updates, and validations.

## Milestone 3: guarded PUB mechanical helper

This milestone adds `python -m groupctl pub`. It is **not** the entire human-to-agent `PUB` workflow: a person/agent must review the diff, check for secrets and unwanted files, select meaningful tests, actually run them, and assess their results. The helper only accepts staged files with a clean remainder of the working tree. It commits and pushes the work, then writes, commits, and pushes an immutable `change_published` event with the exact code commit pinned.

First replace your existing `groupctl/` folder with the one from this ZIP (do not replace your `.git/` or `.group/` folders). From the personal branch `people/P17/setup`:

```powershell
python -m unittest discover -s tests -v
git status --short
git diff
git add groupctl/cli.py
git diff --cached --check
git diff --cached
python -m groupctl pub --summary "Add guarded PUB publication helper" --tests-run "python -m unittest discover -s tests -v"
```

The first `pub` call displays files for confirmation without publishing. Once you've genuinely reviewed the staged diff and validated the tests, rerun it with `--checked`:

```powershell
python -m groupctl pub --summary "Add guarded PUB publication helper" --tests-run "python -m unittest discover -s tests -v" --checked
python -m groupctl sync
```

**Important:** The example above stages only `groupctl/cli.py`. Stage any other intended files deliberately. Do not claim you ran tests if you did not. If your original project already has modifications, inspect them first. You should stage/publish only coherent reviewed changes; never overwrite `.group/`, reinitialize Git, or delete your local identity. If your tests don't pass, investigate before publishing. Do not use `--checked` until the diff and actual validation have been reviewed.
