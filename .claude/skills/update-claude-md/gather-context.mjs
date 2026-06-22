#!/usr/bin/env node
// gather-context.mjs — collects everything needed to decide whether CLAUDE.md
// is stale relative to recent code changes. Read-only: it never writes CLAUDE.md.
//
// Usage:  node gather-context.mjs
// Output: a human/agent-readable report on stdout. Exit 0 always (it's a probe).
//
// What it reports:
//   1. Where CLAUDE.md lives + its size.
//   2. The last commit that actually touched CLAUDE.md.
//   3. Commits made SINCE then that did NOT touch CLAUDE.md (possibly undocumented).
//   4. Uncommitted working-tree changes (staged + unstaged + untracked).
//   5. A doc-relevance flag per changed path (does it live under a dir CLAUDE.md describes?).
//
// Note: shells out via execFileSync('git', [...]) with an argument array — no shell
// is invoked, so paths with spaces are safe and there is no command-injection surface.

import { execFileSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { join, relative } from "node:path";

// Run a git subcommand with explicit args (no shell). Returns trimmed stdout, or "" on error.
function git(...args) {
  try {
    return execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}

// --- locate the git repo root and CLAUDE.md ---------------------------------
const repoRoot = git("rev-parse", "--show-toplevel");
if (!repoRoot) {
  console.error("Not inside a git repository — cannot diff changes. Aborting probe.");
  process.exit(0);
}

// CLAUDE.md is conventionally at repo root; fall back to a tracked search if absent.
let claudeMd = join(repoRoot, "CLAUDE.md");
if (!existsSync(claudeMd)) {
  const found = git("-C", repoRoot, "ls-files", "CLAUDE.md", "**/CLAUDE.md")
    .split("\n").filter(Boolean)[0];
  claudeMd = found ? join(repoRoot, found) : "";
}

const rel = (p) => relative(repoRoot, p).split("\\").join("/");

// Dirs/patterns CLAUDE.md documents — changes here are most likely to need a doc update.
// Tuned for this repo (backend/frontend layered app) but harmless elsewhere.
const DOC_RELEVANT = [
  "backend/app/models",
  "backend/app/services",
  "backend/app/api",
  "backend/app/schemas",
  "backend/app/core",
  "backend/app/main.py",
  "backend/tests",
  "frontend/lib",
  "frontend/components",
  "frontend/app",
  "requirements",
  "package.json",
  "docker-compose",
];
const isDocRelevant = (path) => DOC_RELEVANT.some((d) => path.includes(d));

const out = [];
const log = (s = "") => out.push(s);

log("================ CLAUDE.md staleness report ================");
log(`repo root : ${repoRoot}`);

if (!claudeMd || !existsSync(claudeMd)) {
  log("CLAUDE.md : NOT FOUND — this repo has no CLAUDE.md yet.");
  log("");
  log(">> Recommend CREATING one (see the /init skill) rather than updating.");
  console.log(out.join("\n"));
  process.exit(0);
}

const size = statSync(claudeMd).size;
log(`CLAUDE.md : ${rel(claudeMd)} (${size} bytes)`);

// --- last commit that touched CLAUDE.md -------------------------------------
const lastDocCommit = git("-C", repoRoot, "log", "-1", "--format=%h|%ci|%s", "--", claudeMd);
let sinceRef = "";
if (lastDocCommit) {
  const [hash, date, subj] = lastDocCommit.split("|");
  sinceRef = hash;
  log("");
  log(`Last CLAUDE.md commit: ${hash}  (${date})`);
  log(`                       ${subj}`);
} else {
  log("");
  log("CLAUDE.md is not committed yet (no history) — comparing against full tree.");
}

// --- commits since CLAUDE.md was last touched that did NOT touch it ----------
if (sinceRef) {
  const commitsSince = git("-C", repoRoot, "log", `${sinceRef}..HEAD`, "--format=%h|%ci|%s")
    .split("\n").filter(Boolean);
  log("");
  if (commitsSince.length === 0) {
    log("Commits since last CLAUDE.md update: none.");
  } else {
    log(`Commits since last CLAUDE.md update: ${commitsSince.length} (CLAUDE.md NOT updated in any):`);
    for (const c of commitsSince) {
      const [h, d, s] = c.split("|");
      log(`  - ${h}  ${d.slice(0, 10)}  ${s}`);
    }
    // Which files those commits changed, flagged for doc relevance.
    const files = git("-C", repoRoot, "diff", "--name-only", `${sinceRef}..HEAD`)
      .split("\n").filter(Boolean);
    if (files.length) {
      log("");
      log("  Files changed by those commits (★ = likely needs a CLAUDE.md note):");
      for (const f of files) log(`    ${isDocRelevant(f) ? "★" : " "} ${f}`);
    }
  }
}

// --- uncommitted working-tree changes ---------------------------------------
const statusLines = git("-C", repoRoot, "status", "--short").split("\n").filter(Boolean);
log("");
if (statusLines.length === 0) {
  log("Uncommitted changes: none (working tree clean).");
} else {
  log(`Uncommitted changes: ${statusLines.length} path(s) (★ = likely needs a CLAUDE.md note):`);
  for (const line of statusLines) {
    const path = line.slice(3).trim();
    log(`  ${isDocRelevant(path) ? "★" : " "} ${line}`);
  }
  const diffstat = git("-C", repoRoot, "diff", "--stat");
  if (diffstat) {
    log("");
    log("  Unstaged diffstat:");
    for (const l of diffstat.split("\n")) log(`    ${l}`);
  }
}

log("");
log("============================================================");
log("Next: read CLAUDE.md + the ★ changes, draft specific edits,");
log("then ASK PERMISSION before writing. (See SKILL.md.)");
console.log(out.join("\n"));
