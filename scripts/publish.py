#!/usr/bin/env python3
"""hermes-feed publish <digest-id> — generate Layer B curated digest."""

import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources._base import get_config, get_state_db, log_pipeline


def publish(skill_dir: Path, digest_id: str, force: bool = False):
    conn = get_state_db(skill_dir)
    digest_path = skill_dir / "digests" / f"{digest_id}.md"
    if not digest_path.exists():
        print(f"Digest {digest_id} not found.", file=sys.stderr)
        sys.exit(1)

    # Check if already published
    row = conn.execute("SELECT url FROM publishes WHERE digest_id = ? AND status = 'published'", (digest_id,)).fetchone()
    if row:
        print(f"Already published at {row['url']}")
        return row["url"]

    # Check for feedback
    feedback_path = skill_dir / "feedback" / f"{digest_id}.md"
    if not feedback_path.exists() and not force:
        print(f"No feedback on {digest_id}. Use --force to publish anyway.", file=sys.stderr)
        sys.exit(1)

    digest_content = digest_path.read_text(encoding="utf-8")
    feedback_content = ""
    if feedback_path.exists():
        feedback_content = feedback_path.read_text(encoding="utf-8")

    # Layer B = digest + user comments inline
    published_content = f"# Curated Digest — {digest_id}\n\n"
    published_content += digest_content
    if feedback_content:
        published_content += f"\n\n---\n\n## Curator's Notes\n\n{feedback_content}\n"

    published_dir = skill_dir / "published"
    published_dir.mkdir(exist_ok=True)
    published_path = published_dir / f"{digest_id}.md"
    published_path.write_text(published_content, encoding="utf-8")

    config = get_config(skill_dir)
    base_url = config.get("serve", {}).get("public_base_url", "http://localhost:7700")
    url = f"{base_url}/published/{digest_id}.md"

    conn.execute(
        "INSERT OR REPLACE INTO publishes (digest_id, published_at, url, status) VALUES (?, ?, ?, 'published')",
        (digest_id, datetime.now(timezone.utc).isoformat(), url),
    )
    conn.commit()
    conn.close()

    log_pipeline(skill_dir, "publish", "ok", digest_id=digest_id, url=url)
    print(f"Published: {url}")
    return url


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("digest_id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    publish(SKILL_DIR, args.digest_id, args.force)
