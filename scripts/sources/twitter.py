"""Twitter source adapter via Community Archive Supabase API."""

import sqlite3
from pathlib import Path

from . import _base
from .community_archive import find_account, get_tweets


def fetch_twitter(skill_dir: Path, handle: str, conn: sqlite3.Connection) -> list[dict]:
    source_id = handle.lower().strip("@")

    def fetcher():
        account = find_account(source_id)
        if not account:
            raise ValueError(f"@{source_id} not found in Community Archive")

        tweets = get_tweets(account["account_id"], limit=50)
        items = []
        for tweet in tweets:
            tweet_id = str(tweet.get("tweet_id", ""))
            text = tweet.get("full_text", "")
            created = tweet.get("created_at", "")
            date_str = created[:10] if created else ""
            items.append({
                "id": tweet_id,
                "title": text[:80] + ("..." if len(text) > 80 else ""),
                "url": f"https://x.com/{source_id}/status/{tweet_id}",
                "date": date_str,
                "content": text,
            })
        return items

    return _base.ingest_source(skill_dir, "tw", source_id, fetcher, conn)


def ingest_all(skill_dir: Path, conn: sqlite3.Connection) -> list[dict]:
    config = _base.get_config(skill_dir)
    handles = config.get("sources", {}).get("twitter_community_archive", [])
    all_new = []
    for handle in handles:
        all_new.extend(fetch_twitter(skill_dir, handle, conn))
    return all_new
