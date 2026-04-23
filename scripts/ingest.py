#!/usr/bin/env python3
"""hermes-feed ingest — fetch new items from all configured sources."""

import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources import _base
from sources import substack, twitter, blog


def main():
    conn = _base.get_state_db(SKILL_DIR)
    config = _base.get_config(SKILL_DIR)
    sources = config.get("sources", {})

    total_new = []
    total_errors = 0

    # Substack
    sub_urls = sources.get("substack", [])
    if sub_urls:
        print(f"Substack: {len(sub_urls)} feeds...")
        for i, url in enumerate(sub_urls, 1):
            name = url.split("//")[-1].split(".")[0] if "substack.com" in url else url.split("//")[-1][:30]
            sys.stdout.write(f"  [{i}/{len(sub_urls)}] {name}... ")
            sys.stdout.flush()
            try:
                new = substack.fetch_substack(SKILL_DIR, url, conn)
                print(f"{len(new)} new" if new else "up to date")
                total_new.extend(new)
            except Exception as e:
                print(f"ERROR: {e}")
                total_errors += 1
                _base.log_pipeline(SKILL_DIR, "ingest.sub", "error", source_id=name, error=str(e))

    # Blogs
    blog_urls = sources.get("blog_rss", [])
    if blog_urls:
        print(f"\nBlogs: {len(blog_urls)} feeds...")
        for i, url in enumerate(blog_urls, 1):
            name = url.split("//")[-1].split("/")[0][:30]
            sys.stdout.write(f"  [{i}/{len(blog_urls)}] {name}... ")
            sys.stdout.flush()
            try:
                new = blog.fetch_blog(SKILL_DIR, url, conn)
                print(f"{len(new)} new" if new else "up to date")
                total_new.extend(new)
            except Exception as e:
                print(f"ERROR: {e}")
                total_errors += 1
                _base.log_pipeline(SKILL_DIR, "ingest.blog", "error", source_id=name, error=str(e))

    # Twitter
    tw_handles = sources.get("twitter_community_archive", [])
    if tw_handles:
        print(f"\nTwitter (Community Archive): {len(tw_handles)} accounts...")
        for i, handle in enumerate(tw_handles, 1):
            sys.stdout.write(f"  [{i}/{len(tw_handles)}] @{handle}... ")
            sys.stdout.flush()
            try:
                new = twitter.fetch_twitter(SKILL_DIR, handle, conn)
                print(f"{len(new)} new" if new else "up to date")
                total_new.extend(new)
            except Exception as e:
                print(f"ERROR: {e}")
                total_errors += 1
                _base.log_pipeline(SKILL_DIR, "ingest.tw", "error", source_id=handle, error=str(e))

    # Summary
    print(f"\n{'='*40}")
    print(f"Done. {len(total_new)} new items ingested.")
    if total_errors:
        print(f"  {total_errors} errors (check logs/pipeline.jsonl)")
    conn.close()


if __name__ == "__main__":
    main()
