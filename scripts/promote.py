#!/usr/bin/env python3
"""hermes-feed promote <item-id> — copy a raw item into prestige sources/."""

import shutil
import sys
from pathlib import Path

import yaml
from slugify import slugify

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources._base import get_config, get_state_db, log_pipeline


def promote(skill_dir: Path, item_id: str):
    raw_dir = skill_dir / "feeds" / "raw"
    target = None
    for md_file in raw_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        if f"item_id: {item_id}" in content:
            target = md_file
            break

    if not target:
        print(f"Item {item_id} not found in feeds/raw/.", file=sys.stderr)
        sys.exit(1)

    content = target.read_text(encoding="utf-8")
    # Parse frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])
            body = parts[2].strip()
        else:
            fm, body = {}, content
    else:
        fm, body = {}, content

    title = fm.get("title", item_id)
    title_slug = slugify(title, max_length=60)

    config = get_config(skill_dir)
    sources_dir = Path(config.get("sources_dir", str(skill_dir / "sources")))
    target_dir = sources_dir / title_slug

    # Handle conflict: append -2, -3, etc.
    original_dir = target_dir
    counter = 2
    while target_dir.exists():
        target_dir = original_dir.parent / f"{original_dir.name}-{counter}"
        counter += 1

    target_dir.mkdir(parents=True, exist_ok=True)
    source_md = target_dir / "source.md"
    source_md.write_text(content, encoding="utf-8")

    log_pipeline(skill_dir, "promote", "ok", item_id=item_id, target=str(source_md))
    print(f"Promoted {item_id} → {source_md}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: hermes-feed promote <item-id>", file=sys.stderr)
        sys.exit(1)
    promote(SKILL_DIR, sys.argv[1])
