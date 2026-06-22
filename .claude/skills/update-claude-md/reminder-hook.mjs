#!/usr/bin/env node
// reminder-hook.mjs — PostToolUse(Edit|Write) hook body.
// Reads the hook payload JSON on stdin, and if the edited file looks like
// source code (not docs, not tooling under .claude/), prints a systemMessage
// nudging the user to run /update-claude-md so CLAUDE.md doesn't drift.
//
// Output contract: a single JSON object on stdout (see settings.json hook docs).
// suppressOutput hides the raw stdout from the transcript; systemMessage is the
// visible reminder. Exits 0 and prints nothing for non-code edits.

let data = "";
process.stdin.on("data", (c) => (data += c));
process.stdin.on("end", () => {
  let filePath = "";
  try {
    const payload = JSON.parse(data || "{}");
    filePath = (payload.tool_input && payload.tool_input.file_path) || "";
  } catch {
    return; // malformed payload → stay silent, never break the tool flow
  }

  const normalized = filePath.replace(/\\/g, "/");

  // Skip our own tooling and anything under a .claude/ dir.
  if (normalized.includes("/.claude/") || normalized.startsWith(".claude/")) return;

  // Only nudge for real source files. CLAUDE.md is .md, so editing it never re-nudges.
  if (!/\.(py|ts|tsx|js|jsx|mjs)$/.test(normalized)) return;

  process.stdout.write(
    JSON.stringify({
      systemMessage:
        "📝 Code changed — consider running /update-claude-md to check whether CLAUDE.md needs updating.",
      suppressOutput: true,
    })
  );
});
