"""Blog RSS source adapter using feedparser."""

import sqlite3
from pathlib import Path

import feedparser

from . import _base


def fetch_blog(skill_dir: Path, feed_url: str, conn: sqlite3.Connection) -> list[dict]:
    from slugify import slugify as make_slug
    source_id = make_slug(feed_url, max_length=40)

    def fetcher():
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse feed: {feed_url} ({feed.bozo_exception})")
        items = []
        for entry in feed.entries:
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            published = entry.get("published", "")
            date_str = ""
            if published:
                try:
                    import time
                    t = entry.get("published_parsed")
                    if t:
                        date_str = time.strftime("%Y-%m-%d", t)
                except Exception:
                    pass
            content = ""
            if "content" in entry:
                content = entry.content[0].get("value", "")
            elif "summary" in entry:
                content = entry.summary
            from markdownify import markdownify as md
            content_md = md(content).strip() if content else ""

            entry_id = entry.get("id", link or title[:40])
            items.append({
                "id": entry_id,
                "title": title,
                "url": link,
                "date": date_str,
                "content": content_md,
            })
        return items

    return _base.ingest_source(skill_dir, "blog", source_id, fetcher, conn)


def ingest_all(skill_dir: Path, conn: sqlite3.Connection) -> list[dict]:
    config = _base.get_config(skill_dir)
    urls = config.get("sources", {}).get("blog_rss", [])
    all_new = []
    for url in urls:
        all_new.extend(fetch_blog(skill_dir, url, conn))
    return all_new
