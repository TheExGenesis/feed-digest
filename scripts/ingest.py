#!/usr/bin/env python3
"""hermes-feed ingest — fetch new items from all configured sources."""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources import _base
from sources import substack, twitter, blog


def ingest_source_timed(label, fetch_fn, *args):
    """Run a fetch function, return (label, new_items, elapsed, error).
    
    For threaded calls, pass SKILL_DIR instead of conn — fetch_fn must
    open its own connection.
    """
    t0 = time.time()
    try:
        new = fetch_fn(*args)
        return (label, new, time.time() - t0, None)
    except Exception as e:
        return (label, [], time.time() - t0, str(e))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest feeds")
    parser.add_argument("--since", help="Only ingest items published on or after this date (YYYY-MM-DD)")
    args = parser.parse_args()
    since = args.since

    conn = _base.get_state_db(SKILL_DIR)
    config = _base.get_config(SKILL_DIR)
    sources_cfg = config.get("sources", {})
    if since:
        print(f"Filtering: only items since {since}")

    total_new = []
    total_errors = 0
    t_start = time.time()

    # Substack (RSS — parallel)
    sub_urls = sources_cfg.get("substack", [])
    if sub_urls:
        print(f"Substack: {len(sub_urls)} feeds (parallel)")
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(ingest_source_timed, url.split("//")[-1].split(".")[0] if "substack.com" in url else url.split("//")[-1][:30],
                            substack.fetch_substack, SKILL_DIR, url, None, since): url
                for url in sub_urls
            }
            for future in as_completed(futures):
                label, new, elapsed, error = future.result()
                completed += 1
                if error:
                    print(f"  [{completed}/{len(sub_urls)}] {label}... ERROR ({elapsed:.1f}s): {error}")
                    total_errors += 1
                else:
                    status = f"{len(new)} new" if new else "up to date"
                    print(f"  [{completed}/{len(sub_urls)}] {label}... {status} ({elapsed:.1f}s)")
                    total_new.extend(new)

    # Blogs (RSS — parallel)
    blog_urls = sources_cfg.get("blog_rss", [])
    if blog_urls:
        print(f"\nBlogs: {len(blog_urls)} feeds (parallel)")
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(ingest_source_timed, url.split("//")[-1].split("/")[0][:30],
                            blog.fetch_blog, SKILL_DIR, url, None, since): url
                for url in blog_urls
            }
            for future in as_completed(futures):
                label, new, elapsed, error = future.result()
                completed += 1
                if error:
                    print(f"  [{completed}/{len(blog_urls)}] {label}... ERROR ({elapsed:.1f}s): {error}")
                    total_errors += 1
                else:
                    status = f"{len(new)} new" if new else "up to date"
                    print(f"  [{completed}/{len(blog_urls)}] {label}... {status} ({elapsed:.1f}s)")
                    total_new.extend(new)

    # Twitter (API calls — parallelize with thread pool)
    tw_handles = sources_cfg.get("twitter_community_archive", [])
    if tw_handles:
        print(f"\nTwitter (Community Archive): {len(tw_handles)} accounts (parallel)")
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(ingest_source_timed, handle, twitter.fetch_twitter, SKILL_DIR, handle, None, since): handle
                for handle in tw_handles
            }
            for future in as_completed(futures):
                handle, new, elapsed, error = future.result()
                completed += 1
                if error:
                    print(f"  [{completed}/{len(tw_handles)}] @{handle}... ERROR ({elapsed:.1f}s): {error}")
                    total_errors += 1
                else:
                    status = f"{len(new)} new" if new else "up to date"
                    print(f"  [{completed}/{len(tw_handles)}] @{handle}... {status} ({elapsed:.1f}s)")
                    total_new.extend(new)

    # Summary
    total_elapsed = time.time() - t_start
    print(f"\n{'='*40}")
    print(f"Done in {total_elapsed:.1f}s. {len(total_new)} new items ingested.")
    if total_errors:
        print(f"  {total_errors} errors (check logs/pipeline.jsonl)")
    conn.close()


if __name__ == "__main__":
    main()
