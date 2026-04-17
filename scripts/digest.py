#!/usr/bin/env python3
"""hermes-feed digest — compose a daily digest from recent raw items + past digests + memory + feedback."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources._base import get_config, get_state_db, log_pipeline

MAX_FILE_TOKENS = 20_000
HARD_SKIP_TOKENS = 200_000
TOTAL_BUDGET_TOKENS = 150_000
CHARS_PER_TOKEN = 4  # rough estimate


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def truncate_if_needed(text: str, max_tokens: int = MAX_FILE_TOKENS) -> str:
    tokens = estimate_tokens(text)
    if tokens <= max_tokens:
        return text
    head_chars = 10_000 * CHARS_PER_TOKEN
    tail_chars = 5_000 * CHARS_PER_TOKEN
    return text[:head_chars] + "\n\n[... middle elided ...]\n\n" + text[-tail_chars:]


def collect_raw_items(skill_dir: Path, from_date: str, to_date: str) -> list[dict]:
    raw_dir = skill_dir / "feeds" / "raw"
    if not raw_dir.exists():
        return []
    items = []
    for md_file in raw_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        if estimate_tokens(content) > HARD_SKIP_TOKENS:
            log_pipeline(skill_dir, "digest.collect", "hard_skip",
                         file=str(md_file), tokens=estimate_tokens(content))
            continue
        # Check date from filename or frontmatter
        name = md_file.stem
        file_date = name[:10] if len(name) >= 10 and name[4] == "-" else ""
        if file_date and (file_date < from_date or file_date > to_date):
            continue
        items.append({
            "path": str(md_file),
            "content": truncate_if_needed(content),
            "date": file_date,
        })
    return items


def collect_past_digests(skill_dir: Path, days: int = 7) -> str:
    digests_dir = skill_dir / "digests"
    if not digests_dir.exists():
        return ""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    parts = []
    for f in sorted(digests_dir.glob("*.md")):
        if f.stem >= cutoff:
            parts.append(f"## Past digest: {f.stem}\n\n{f.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n---\n\n".join(parts)


def collect_memory(skill_dir: Path) -> str:
    config = get_config(skill_dir)
    memory_path = Path(os.path.expanduser(config.get("memory_path", "")))
    if not memory_path.exists():
        return "(No memory folder configured or found.)"
    parts = []
    for f in sorted(memory_path.rglob("*.md"))[:50]:  # cap at 50 files
        content = f.read_text(encoding="utf-8", errors="replace")
        content = truncate_if_needed(content, 5000)
        parts.append(f"### Memory: {f.relative_to(memory_path)}\n\n{content}")
    return "\n\n".join(parts)


def collect_feedback(skill_dir: Path) -> str:
    feedback_dir = skill_dir / "feedback"
    if not feedback_dir.exists():
        return ""
    parts = []
    for f in sorted(feedback_dir.glob("*.md"))[-14:]:  # last 14 feedback files
        parts.append(f"### Feedback on {f.stem}\n\n{f.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n".join(parts)


def compose_digest(skill_dir: Path, from_date: str, to_date: str):
    config = get_config(skill_dir)
    conn = get_state_db(skill_dir)

    # Collect inputs
    raw_items = collect_raw_items(skill_dir, from_date, to_date)
    if not raw_items:
        log_pipeline(skill_dir, "digest", "skipped_no_new_items",
                     from_date=from_date, to_date=to_date)
        print("No new items in range. Skipping digest.")
        conn.close()
        return None

    window = config.get("digest", {}).get("integration_window_days", 7)
    past_digests = collect_past_digests(skill_dir, window)
    memory = collect_memory(skill_dir)
    feedback = collect_feedback(skill_dir)

    # Load prompt template
    prompt_path = skill_dir / "prompts" / "digest.md"
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    # Assemble context
    raw_section = "\n\n---\n\n".join(
        f"### [{i+1}] {item.get('date', '')} — {Path(item['path']).parent.name}\n\n{item['content']}"
        for i, item in enumerate(raw_items)
    )

    # Budget check — prune oldest raw items if over budget
    total_text = raw_section + past_digests + memory + feedback + prompt_template
    while estimate_tokens(total_text) > TOTAL_BUDGET_TOKENS and raw_items:
        raw_items.pop(0)  # drop oldest
        raw_section = "\n\n---\n\n".join(
            f"### [{i+1}] {item.get('date', '')} — {Path(item['path']).parent.name}\n\n{item['content']}"
            for i, item in enumerate(raw_items)
        )
        total_text = raw_section + past_digests + memory + feedback + prompt_template

    user_message = f"""## Today's new items ({from_date} to {to_date})

{raw_section}

## Past digests (last {window} days)

{past_digests or "(First digest — no history yet.)"}

## User memory

{memory}

## Accumulated feedback on past digests

{feedback or "(No feedback yet.)"}
"""

    # Call LLM via OpenRouter (OpenAI-compatible)
    import openai
    llm_config = config.get("llm", {})
    api_key_env = llm_config.get("api_key_env", "OPENROUTER_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        # Fallback: try loading from .env file
        env_path = skill_dir / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith(f"{api_key_env}="):
                    api_key = line.split("=", 1)[1].strip()
    if not api_key:
        log_pipeline(skill_dir, "digest", "llm_error", error=f"missing {api_key_env}")
        print(f"LLM API key not set. Export {api_key_env} or run setup.py.")
        conn.close()
        return None

    base_url = llm_config.get("base_url", "https://openrouter.ai/api/v1")
    model = llm_config.get("model", "anthropic/claude-sonnet-4")
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    digest_id = to_date

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_message},
            ],
        )
        digest_content = response.choices[0].message.content
    except Exception as e:
        log_pipeline(skill_dir, "digest", "llm_error", error=str(e))
        failures_dir = skill_dir / "failures"
        failures_dir.mkdir(exist_ok=True)
        (failures_dir / f"{digest_id}.md").write_text(str(e), encoding="utf-8")
        print(f"LLM call failed: {e}")
        conn.close()
        return None

    # Write digest
    digests_dir = skill_dir / "digests"
    digests_dir.mkdir(exist_ok=True)
    digest_path = digests_dir / f"{digest_id}.md"
    digest_path.write_text(digest_content, encoding="utf-8")

    conn.execute(
        "INSERT OR REPLACE INTO digests (digest_id, created_at, status, raw_item_count, token_estimate) VALUES (?, ?, ?, ?, ?)",
        (digest_id, datetime.now(timezone.utc).isoformat(), "composed",
         len(raw_items), estimate_tokens(total_text)),
    )
    conn.commit()
    conn.close()

    log_pipeline(skill_dir, "digest", "ok",
                 digest_id=digest_id, raw_items=len(raw_items),
                 token_estimate=estimate_tokens(total_text))
    print(f"Digest written: {digest_path}")
    print(f"  Items: {len(raw_items)}, Tokens: ~{estimate_tokens(total_text)}")
    return str(digest_path)


def main():
    parser = argparse.ArgumentParser(description="Compose a feed digest")
    parser.add_argument("--from", dest="from_date",
                        default=(datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"))
    parser.add_argument("--to", dest="to_date",
                        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    compose_digest(SKILL_DIR, args.from_date, args.to_date)


if __name__ == "__main__":
    main()
