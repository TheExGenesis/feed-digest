# feed-digest

A shareable agent skill that produces a daily digest from your feeds — Twitter (via community archive), Substacks, blogs. Memory-aware. Self-improving: you give feedback in your 1:1 agent chat, next day's digest adapts.

Built by Francisco (Xiq) and Ivan, intended to be portable across agent harnesses (Hermes, Claude Code, anything with file-edit + Telegram/email tool access).

## Status

Pre-scaffolding. The design and test plan are in `docs/`. Implementation starts next.

**If you're an AI agent picking this up: read [`AGENTS.md`](AGENTS.md) first.** It tells you to study gstack as a reference for skill-authoring style, explains the build order, lists the critical rules, and sets up the handoff protocol. Then `docs/design.md` → `docs/test-plan.md` for the full context.

## Install

```bash
git clone https://github.com/TheExGenesis/feed-digest
cd feed-digest
./install
```

The install script detects whether Hermes or Claude Code is installed and symlinks the repo into the appropriate skills directory (`~/.hermes/skills/feed-digest` or `~/.claude/skills/feed-digest`). Re-running `./install` is idempotent.

## How it works (once built)

Cron fires daily at your configured time (default 07:00). The pipeline:

1. **Ingest** — fetch new items from each configured source into `feeds/raw/<type>/<source-id>/<date>.md`.
2. **Compose** — read past 7 days of digests + your memory folder + accumulated feedback, produce `digests/YYYY-MM-DD.md`.
3. **Deliver** — your host agent reads the new digest and sends it to you via email and/or 1:1 Telegram.
4. **Feedback** — you reply to the digest in your normal agent chat. Agent detects feedback and writes it to `feedback/<digest-id>.md`. Tomorrow's digest adapts.
5. **Publish (Layer B, optional)** — agent asks "publish a curated version?" You say yes. Agent runs `hermes-feed publish <digest-id>`. A stable-URL "link post" is generated and shared with your followers or group chat.

No listener daemon. No bot registration (the skill uses your existing agent's Telegram access). Just cron + markdown + the host agent as the orchestrator.

## Config

First run copies `config.example.yaml` to `config.yaml` (which is gitignored). Edit `config.yaml`:

```yaml
memory_path: ~/hermes/memory          # your personal memory folder (read-only)
timezone: America/New_York
email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  smtp_user: you@gmail.com
  smtp_password_env: FEED_SMTP_PASSWORD
  to: you@example.com
sources:
  substack:
    - https://xiqo.substack.com
  twitter_community_archive:
    - frsc
  blog_rss:
    - https://example.com/feed.xml
```

Secrets (SMTP password, any API keys) are read from env vars, never committed.

## Docs

- [Design](docs/design.md) — problem, premises, architecture, build order.
- [Test Plan](docs/test-plan.md) — coverage diagram, fixtures, eval scenarios.
