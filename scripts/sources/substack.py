"""Substack source adapter using RSS feeds (fast) instead of substack-api (slow, rate-limited)."""

import sqlite3
from pathlib import Path

import feedparser
from markdownify import markdownify as md

from . import _base


def fetch_substack(skill_dir: Path, substack_url: str, conn: sqlite3.Connection, since: str = None) -> list[dict]:
    # Normalize URL and derive RSS feed URL
    url = substack_url.rstrip("/")
    source_id = url.split("//")[-1].split(".")[0]
    if url.split("//")[-1].startswith("www."):
        source_id = url.split("//")[-1].split("/")[0]

    # Every Substack has /feed as RSS
    feed_url = f"{url}/feed"

    def fetcher():
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse feed: {feed_url}")
        items = []
        for entry in feed.entries:
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            published = entry.get("published", "")
            date_str = ""
            if published:
                t = entry.get("published_parsed")
                if t:
                    import time
                    date_str = time.strftime("%Y-%m-%d", t)

            # Get content (Substack RSS includes full post HTML)
            content_html = ""
            if "content" in entry:
                content_html = entry.content[0].get("value", "")
            elif "summary" in entry:
                content_html = entry.summary
            content_md = md(content_html).strip() if content_html else ""

            # Use link as unique ID (stable across runs)
            entry_id = entry.get("id", link or title[:40])

            items.append({
                "id": entry_id,
                "title": title,
                "url": link,
                "date": date_str,
                "content": content_md,
            })
        return items

    return _base.ingest_source(skill_dir, "sub", source_id, fetcher, conn, since=since)


def ingest_all(skill_dir: Path, conn: sqlite3.Connection, since: str = None) -> list[dict]:
    config = _base.get_config(skill_dir)
    urls = config.get("sources", {}).get("substack", [])
    all_new = []
    for url in urls:
        all_new.extend(fetch_substack(skill_dir, url, conn, since=since))
    return all_new
