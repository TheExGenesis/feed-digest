---
name: feed-digest
description: |
  Daily digest of the user's feeds (Twitter community archive, Substacks, blogs).
  Memory-aware. Self-improving via user feedback captured in the host agent's 1:1 chat.
  The host agent (Hermes, Claude Code, etc.) is the orchestrator — this skill provides
  CLI primitives (ingest, digest, deliver, promote, publish) and instructions for the agent.
triggers:
  - "digest"
  - "what's new today"
  - "feed digest"
  - "daily digest"
  - "publish the digest"
  - "save this to sources"
  - "promote to sources"
---

# feed-digest SKILL — Full Operating Manual

> **STATUS: scaffold only.** The CLI primitives below are specified but not yet implemented.
> See `docs/design.md` and `docs/test-plan.md` for the plan. This SKILL.md will be
> the load-bearing instruction set once the skill ships.

## What this skill produces

A daily markdown digest at `digests/YYYY-MM-DD.md`. The host agent is responsible for:
reading the new digest, sending it to the user via email and/or 1:1 Telegram,
detecting feedback in the user's reply messages, routing feedback to `feedback/<digest-id>.md`,
and prompting the user to publish a curated "Layer B" version.

The cron-driven pipeline is pure fetch-and-compose. Everything user-facing happens
through the host agent.

## Setup (first run)

1. Check that `config.yaml` exists at the skill root. If missing, copy
   `config.example.yaml` to `config.yaml` and prompt the user to fill in:
   memory path, timezone, email SMTP settings, source lists.
2. Verify `~/.hermes/skills/feed-digest` (or `~/.claude/skills/feed-digest`) points
   at the repo via `./install`. Re-run `./install` if not.
3. Install the crontab entry from `crontab.example` (once `pyproject.toml` and deps are in place).

## Daily flow (host agent's job)

Every morning:
1. Check `digests/` for new files not yet delivered (query state via `hermes-feed status`).
2. Read the latest undelivered digest markdown.
3. Format for the user's preferred surface. If email: send. If Telegram: post.
4. Mark delivered (`hermes-feed mark-delivered <digest-id>`).

## Feedback detection

When the user sends any message in your 1:1 chat, check if it is feedback on a recent digest. Pattern-match phrases like:

- "more like X", "less of Y", "that was good", "that wasn't"
- "save this", "save the one about Z", "pull that into sources"
- Direct reference to a digest item by topic or author
- Direct reference to an item-id shown in a digest (e.g., `[tw-abc12]`, `[sub-def34]`)

If the message references a recent digest (within 24h of delivery), treat as feedback.

## Feedback writing

Append to `<skill-dir>/feedback/<digest-id>.md`:
- ISO timestamp
- User's verbatim message (never discard)
- Optional inferred tags in YAML frontmatter:
  - `promote: <item-id>` (user wants to save to prestige sources)
  - `don't_feature: <source-id>` (user dislikes a source)
  - `tone: positive | negative | neutral`

Then respond to the user in chat confirming what you wrote.

## Item-id lookup

Digests include item-ids inline (`[tw-abc12]`, `[sub-def34]`). When the user references an item by name or topic instead of ID, grep the latest digest markdown for matching text and resolve to the item-id.

## Command invocation

Map user language to CLI calls:

| User says | Run |
|-----------|-----|
| "save this", "pull to sources" | `hermes-feed promote <item-id>` |
| "publish today's digest" | `hermes-feed publish <digest-id>` |
| "republish" | `hermes-feed republish <digest-id>` |
| "rerun for last week" | `hermes-feed digest --from YYYY-MM-DD --to YYYY-MM-DD` |
| "what did I save this week?" | grep in `sources/` for recent `date:` frontmatter |

## Publish gate (Layer B)

If the latest digest has at least one feedback entry AND has not been published or skipped, prompt the user:

> *"I have your feedback on <digest-id>. Want me to publish a curated version? (yes / no / skip)"*

- `yes` → run `hermes-feed publish <digest-id>`, post URL to configured output channels.
- `no` → wait for more feedback, re-ask the next morning.
- `skip` → mark terminal, don't ask again for this digest.

If the user ignores the prompt three days running, stop asking and auto-skip.

## Republish

If the user asks to republish a digest because new feedback arrived after the initial publish, run `hermes-feed republish <digest-id>`. The published file is regenerated with all current feedback included.

## Error recovery

If any CLI call exits non-zero, tell the user exactly what failed and link to `logs/pipeline.jsonl`. Do not silently retry more than once. Do not try to "fix" ingestion or config problems yourself — report them.

## Host-agent-agnostic

This skill doesn't assume Hermes. Any agent with file-edit, email, and (ideally) Telegram tool access can drive it. Xiq runs Hermes; Ivan runs his own agent; both follow these same instructions.

## CLI reference (scripts/*.py — to be implemented)

| Command | Purpose |
|---------|---------|
| `hermes-feed ingest` | Fetch new items from all configured sources |
| `hermes-feed digest [--from YYYY-MM-DD] [--to YYYY-MM-DD]` | Compose digest for the range (default: today) |
| `hermes-feed deliver` | Optional CLI fallback: send latest digest via email |
| `hermes-feed promote <item-id>` | Copy a raw item into prestige `sources/` |
| `hermes-feed publish <digest-id>` | Generate Layer B curated digest with stable URL |
| `hermes-feed republish <digest-id>` | Regenerate Layer B after new feedback |
| `hermes-feed status` | Show pipeline state (last ingest, last digest, undelivered items) |
| `hermes-feed latest-digest-id` | Return the most recent delivered digest-id |
| `hermes-feed mark-delivered <digest-id>` | Record that the host agent sent a digest |
