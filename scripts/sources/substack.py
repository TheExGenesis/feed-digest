"""Substack source adapter using substack-api."""

import sqlite3
from pathlib import Path

from markdownify import markdownify as md
from substack_api import Newsletter

from . import _base


def fetch_substack(skill_dir: Path, substack_url: str, conn: sqlite3.Connection) -> list[dict]:
    source_id = substack_url.rstrip("/").split("//")[-1].split(".")[0]

    def fetcher():
        newsletter = Newsletter(substack_url)
        posts = newsletter.get_posts(limit=50)
        items = []
        for post in posts:
            try:
                meta = post.get_metadata()
                title = meta.get("title", "Untitled")
                post_date = meta.get("post_date", "")
                date_str = post_date[:10] if post_date else ""
                body_html = meta.get("body_html", "")
                body_md = md(body_html).strip() if body_html else ""
                canonical = meta.get("canonical_url", post.url if hasattr(post, "url") else "")
                slug = meta.get("slug", "")
                items.append({
                    "id": slug or title[:40],
                    "title": title,
                    "url": canonical,
                    "date": date_str,
                    "content": body_md,
                })
            except Exception:
                continue
        return items

    return _base.ingest_source(skill_dir, "sub", source_id, fetcher, conn)


def ingest_all(skill_dir: Path, conn: sqlite3.Connection) -> list[dict]:
    config = _base.get_config(skill_dir)
    urls = config.get("sources", {}).get("substack", [])
    all_new = []
    for url in urls:
        all_new.extend(fetch_substack(skill_dir, url, conn))
    return all_new
