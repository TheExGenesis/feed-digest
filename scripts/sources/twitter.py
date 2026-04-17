"""Twitter source adapter via community archive API."""

import sqlite3
from pathlib import Path

import requests

from . import _base

COMMUNITY_ARCHIVE_API = "https://api.communityarchive.org/v1"


def fetch_twitter(skill_dir: Path, handle: str, conn: sqlite3.Connection) -> list[dict]:
    source_id = handle.lower().strip("@")

    def fetcher():
        resp = requests.get(
            f"{COMMUNITY_ARCHIVE_API}/users/{source_id}/tweets",
            params={"limit": 50, "sort": "date_desc"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        tweets = data if isinstance(data, list) else data.get("tweets", data.get("data", []))
        items = []
        for tweet in tweets:
            tweet_id = str(tweet.get("id", tweet.get("tweet_id", "")))
            text = tweet.get("text", tweet.get("full_text", ""))
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
