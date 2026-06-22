---
name: update-claude-md
description: Check whether CLAUDE.md is stale after code changes and update it — ALWAYS asking permission before writing. Use after editing code, before/after a commit, or when the user says "update CLAUDE.md", "sync the docs", "document these changes", "did the docs drift", or "remind me to update CLAUDE.md".
---

# update-claude-md

Keeps `CLAUDE.md` in sync with the code. CLAUDE.md is the project brief Claude
loads every session, so when it drifts from reality every future session starts
with wrong assumptions. This skill detects that drift and proposes precise edits
— but **never writes CLAUDE.md without explicit user permission.**

It is driven by a read-only probe, `gather-context.mjs`, which reports what
changed since CLAUDE.md was last updated. Paths below are relative to the repo
root.

## When to run

- After making code changes (new model/service/route/schema, changed conventions,
  new tests, changed commands).
- Before or just after committing.
- Whenever the user asks to update / sync / check the docs.

> Auto-trigger note: a skill only runs when invoked or auto-loaded by request —
> it does **not** fire automatically after every edit. To get a real "remind me
> after each code change" prompt, add a PostToolUse hook (see *Auto-reminder
> hook* at the bottom).

## Step 1 — Run the probe (agent path)

```bash
node .claude/skills/update-claude-md/gather-context.mjs
```

It prints, read-only (never writes):
- Where CLAUDE.md lives and its size.
- The last commit that touched CLAUDE.md.
- Commits made **since** then that did **not** update CLAUDE.md (likely undocumented).
- Uncommitted working-tree changes.
- A `★` next to each changed path that lives under a directory CLAUDE.md
  documents (models, services, api, schemas, core, tests, frontend, deps) — those
  are the changes most likely to need a doc note.

If it reports `CLAUDE.md : NOT FOUND`, stop and recommend `/init` to create one
instead.

## Step 2 — Read the real changes

For each `★` path, look at the actual diff (don't guess from filenames):

```bash
git diff HEAD~1 -- backend/app/services/issue_service.py   # a committed change
git diff -- backend/app/api/routes/imports.py              # an uncommitted change
```

Then read the current `CLAUDE.md` and find the section(s) those changes affect
(e.g. a new route → the route list; a new model → the model list; new tests → the
test count in **Status**).

## Step 3 — Draft specific edits

Write concrete proposed edits, not vague intentions. Good drafts name the exact
section and the exact text. Common things that drift in this repo:
- The **Status** line's test counts and "Built so far" list.
- Per-feature sections when a new model/service/route/schema is added.
- **Conventions & gotchas** when a new pattern or constraint is introduced.

## Step 4 — ASK PERMISSION (hard gate)

**Do not edit CLAUDE.md yet.** Present the proposed edits to the user and ask for
explicit approval, e.g.:

> CLAUDE.md looks stale vs. commit `<hash>`. I propose these edits:
> 1. Under **Status**: bump tests 75 → 79, add "Workspace model" to Built so far.
> 2. Add a **Workspace** section documenting the model/service/route.
> Apply these to CLAUDE.md? (yes / edit / no)

Only after the user says yes do you proceed. If they say "edit", revise and ask
again. If "no", stop without touching the file.

## Step 5 — Apply (only on approval)

Use the `Edit` tool to apply exactly the approved changes to `CLAUDE.md`. Keep
edits surgical — match the existing tone and structure; don't rewrite sections
that didn't change. Do not commit unless the user asks.

## Gotchas

- **Permission is mandatory.** This skill's whole point is *asking* before
  writing CLAUDE.md. Never skip Step 4, even for a one-line change.
- The probe shells out via `execFileSync("git", [...])` (no shell) so the repo
  path's space (`Claude code-2`) is handled and there's no injection surface.
- The `★` flag is a heuristic, not truth — a starred file may need no doc change,
  and an unstarred one occasionally does. Always read the diff.
- `gather-context.mjs` is read-only by design. The *only* thing that writes
  CLAUDE.md is you, via `Edit`, in Step 5, after approval.

## Auto-reminder hook (optional, set up separately)

To actually be *reminded* after each code change (rather than remembering to run
this), add a PostToolUse hook on `Edit|Write` in `.claude/settings.json` that
prints a reminder to run `/update-claude-md`. A skill can't self-trigger; the
harness runs hooks. Ask the user, then use the `update-config` skill to add it —
e.g. a hook whose command echoes "Code changed — consider `/update-claude-md`."
