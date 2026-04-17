#!/usr/bin/env python3
"""hermes-feed ingest — fetch new items from all configured sources."""

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources import _base
from sources import substack, twitter, blog


def main():
    conn = _base.get_state_db(SKILL_DIR)
    config = _base.get_config(SKILL_DIR)

    total_new = []
    for adapter in [substack, blog, twitter]:
        try:
            new = adapter.ingest_all(SKILL_DIR, conn)
            total_new.extend(new)
        except Exception as e:
            _base.log_pipeline(SKILL_DIR, f"ingest.{adapter.__name__}", "error", error=str(e))

    print(f"Ingested {len(total_new)} new items.")
    if total_new:
        for item in total_new:
            print(f"  [{item['item_id']}] {item.get('title', '')[:60]}")
    conn.close()


if __name__ == "__main__":
    main()
