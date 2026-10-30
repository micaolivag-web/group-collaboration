# Local AI Agent Instructions (Protocol 0.1)

You are working as one human+AI pair in a shared repository. Read the authoritative `specs/00_group_collaboration_assignment.md` and the companion documents `specs/01_*.md` through `specs/07_*.md` before operating on collaboration state.

Human prompt shorthand (NOT names of necessarily implemented `groupctl` CLI subcommands):

- `SYNC`: Follow `specs/05_command_procedures.md` §1; never blindly integrate unrelated feature branches.
- `PUB`: Follow §2; inspect changes, test, commit and push a personal branch, then publish a `change_published` event. Never claim publication until pushed.
- `INT <change_id>`: Follow §3; inspect referenced event AND actual diff, integrate deliberately, validate mechanically and semantically, publish an `integration_result`.
- `REV <change_id>`: Follow §4; inspect real diff and tests, publish a `review` WITHOUT merging.
- `TEST [scope]`: Follow §5; test exact commit and publish meaningful `test_result` evidence.
- `STATUS`: Follow §6; report identity, Git state, new events, blockers, and next action without modifying code unnecessarily.
- `FINAL`: Follow §7; propose candidate from canonical state; display it to human; publish final files ONLY after confirmation.

Do not interpret an ordinary successful Git merge as proof of correctness. Never invent test results, statuses, event fields, commit IDs or remote publication. Preserve unique immutable event files under `.group/events/`. Keep personal identity/cache under ignored `.group/local/`. The `groupctl` application is currently **incomplete**, starting with initialization, joining and local status only; when a procedure requires missing functionality, report that limitation instead of pretending it worked. Use Git and simple tools where appropriate; use AI judgment for semantic review and safe conflict resolution.
