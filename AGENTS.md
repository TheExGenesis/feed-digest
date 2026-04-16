# AGENTS.md — instructions for the next AI agent

You are an AI agent (Claude Code, Hermes, or similar) picking up implementation of this skill. Read this file first, then `docs/design.md`, then `docs/test-plan.md`. Together they have the full context.

---

## TL;DR of where we are

The skill has been designed, engineering-reviewed, and approved. **No code has been written yet.** Your job is to scaffold the Python package and implement the components in `docs/design.md` → "Next Steps" section, writing tests as you go per `docs/test-plan.md`.

---

## Before you start — learn from gstack

This repo is an **agent skill** in the style defined by the open Agent Skills spec (Anthropic Dec 2025, adopted by OpenAI Codex and Claude Code). The canonical reference implementation is **gstack** — a framework of well-written skills by Garry Tan. Study it before you design your own file layout, CLI conventions, or SKILL.md prose.

**If gstack is not already cloned at `~/.claude/skills/gstack/` or `~/.hermes/skills/gstack/`:**

```bash
# Pick the install location that matches your host
if [ -d "$HOME/.hermes/skills" ]; then
  DEST="$HOME/.hermes/skills/gstack"
elif [ -d "$HOME/.claude/skills" ]; then
  DEST="$HOME/.claude/skills/gstack"
else
  mkdir -p "$HOME/.claude/skills"
  DEST="$HOME/.claude/skills/gstack"
fi
git clone https://github.com/garrytan/gstack "$DEST"
cd "$DEST" && ./setup
```

**Read as examples of good skills** (don't copy wholesale — learn the style):

- `gstack/office-hours/SKILL.md` — how a skill can be a phased interactive workflow with AskUserQuestion gates. Teaches SKILL.md as executable instructions.
- `gstack/review/SKILL.md` — how a skill wraps existing project tools (type checker, linter, tests) and produces a composite score. Good pattern for a "pipeline" skill.
- `gstack/browse/SKILL.md` + `gstack/browse/dist/browse` — how a skill ships a compiled CLI binary alongside prose instructions. Clean separation between "agent reads SKILL.md" and "agent runs CLI tool" — which is exactly our model.
- `gstack/ship/SKILL.md` — how a skill orchestrates a multi-step workflow (detect base branch, run tests, review diff, push, create PR). Good reference for our daily pipeline.
- `gstack/bin/gstack-*` scripts — how gstack names its CLI helpers and organizes them in a `bin/` directory.

What to take from gstack:
- **Style of SKILL.md prose** — imperative instructions to the agent, not descriptive prose about the feature. Our SKILL.md should tell the agent what to DO, not what the skill IS.
- **CLI-as-primitive pattern** — the skill ships scripts; SKILL.md instructs the agent to call them. The agent orchestrates. We're doing the same.
- **Config + state directory conventions** — gstack puts runtime state in `~/.gstack/`; we use `.feed/` inside the repo.
- **Setup script that's idempotent** — see `gstack/setup`. Our `./install` already follows this pattern.

What NOT to copy:
- gstack has many internal abstractions (telemetry, session tracking, learnings) we don't need. Keep feed-digest lean. Just ingest → compose → deliver → feedback.
- gstack's preamble pattern (every skill runs `gstack-update-check` etc. on load) is overkill for us. One skill, one job.

---

## After you've studied gstack — what to build

Read `docs/design.md` end-to-end. The "Recommended Approach → A, designed so B is easy" section has the build order as numbered steps 1–14. Start at step 1.

Implement in order:

1. **Scaffold** — `pyproject.toml` (Python 3.11+, deps: `feedparser`, `substack-api`, `anthropic`, `python-slugify`, `pyyaml`, `zoneinfo` stdlib). Create `scripts/`, `feedback/`, `prompts/` dirs inside the repo.
2. **sources/_base.py** — shared `ingest_source()` helper per the Code Quality section of `docs/design.md`.
3. **sources/substack.py** — port the working pattern from `hermes-workspace/scripts/substack-sync.py` (this same user wrote it; copy it here, strip Hermes-specific hooks).
4. **sources/twitter.py** — community archive API. Verify the API + that each configured handle is in-archive BEFORE writing the adapter (docs/design.md flags this as a prerequisite).
5. **sources/blog.py** — feedparser-based RSS.
6. **digest.py** — the central pipeline. Hardcoded single-pass defaults per `docs/design.md` Build step 3. One Claude Sonnet call. No sub-agents, no strategy flags in MVP.
7. **state.db migrations** — numbered SQL files in `migrations/`. Schema per `docs/test-plan.md`.
8. **deliver.py** — SMTP email sender (fallback CLI). Telegram delivery is host-agent-owned.
9. **serve.py** — static file host on configured port (simplest thing: `python -m http.server` wrapped with a slug-routed redirect).
10. **publish.py** + **republish** — Layer B curation.
11. **promote.py** — promote raw item to prestige `sources/`.
12. **crontab.example** — document the cron line.

**Write tests alongside each module.** The coverage diagram in `docs/test-plan.md` lists 26 code paths; each one needs a test before you can call that module done. Use pytest + monkeypatch + tmp_path (matching the user's hermes-workspace convention).

---

## Critical rules

- **Never import from or depend on `hermes_log.py` or anything in `~/hermes/`.** This skill must work for Ivan (who doesn't have Hermes). Copy code patterns; don't import.
- **Config secrets via env vars.** `config.yaml` holds the env var NAMES (`smtp_password_env: FEED_SMTP_PASSWORD`), never the values. `config.yaml` is gitignored.
- **Feedback lives in `feedback/<digest-id>.md` (inside this repo).** Not in the user's memory folder. The skill is self-improving via its own local feedback dir.
- **Item-ids are prefixed by source type** (`tw-xxx`, `sub-xxx`, `blog-xxx`). Prevents collisions.
- **Empty-day digest = SKIP.** No LLM call, no file write, just a `pipeline.jsonl` log entry.
- **Promote conflict = append `-2` suffix** to the slug. Both files preserved.
- **LLM failures: 3x SDK-level retry, then skip-today.** Don't block the pipeline.
- **Layer B is a human-curation pass on Layer A, not a re-summarization.** Delete un-starred items, inline user comments, done.

---

## When you hit an ambiguity

Use the Confusion Protocol (from gstack's ETHOS if you've studied it, or just common sense): if there are two plausible architectures for something and you're not sure, STOP and ask the user. Do not guess on data models, folder layouts, or prompt structure — those decisions compound.

Examples of decisions you should push back on, not guess:
- Exact prompt for `prompts/digest.md` — user will want to iterate on this directly.
- Whether to use `anthropic.Anthropic()` or the async variant — ask which fits the user's stack.
- Whether the CLI is `hermes-feed` or renamed — confirm with user if not explicit in design.

Examples of decisions that are obviously one way:
- Python stdlib over third-party where equivalent (`zoneinfo` over `pytz`).
- pytest over unittest (user's existing convention).
- Idempotent writes in every adapter (design doc mandates).

---

## Handoff protocol

After every logical chunk of work (e.g., finished all source adapters; finished digest.py; finished test coverage for one module):

1. Run the tests that exist: `pytest tests/ -x -v`.
2. Commit with a descriptive message. Reference `docs/design.md` section if applicable.
3. Push to origin/main.
4. Report to the user what's done and what's next.

The user may pick up this work on a different machine (local or server at `frsc@65.108.63.153`). Commits and pushes make your progress portable.

Good luck. Build something people want.
