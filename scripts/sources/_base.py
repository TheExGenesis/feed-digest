"""Base ingestion helper shared by all source adapters."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml
from slugify import slugify


def get_config(skill_dir: Path) -> dict:
    config_path = skill_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}. Run ./install first.")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_state_db(skill_dir: Path) -> sqlite3.Connection:
    db_path = skill_dir / ".feed" / "state.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _run_migrations(conn, skill_dir)
    return conn


def _run_migrations(conn: sqlite3.Connection, skill_dir: Path):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )
    """)
    current = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
    migrations_dir = skill_dir / "migrations"
    if not migrations_dir.exists():
        return
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        version = int(sql_file.stem.split("_")[0])
        if version > current:
            with open(sql_file) as f:
                conn.executescript(f.read())
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.commit()


def log_pipeline(skill_dir: Path, stage: str, status: str, **extra):
    log_path = skill_dir / "logs" / "pipeline.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": status,
        **extra,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def ingest_source(
    skill_dir: Path,
    source_type: str,
    source_id: str,
    fetcher_fn: Callable,
    conn: sqlite3.Connection,
    max_retries: int = 3,
    since: str = None,
) -> list[dict]:
    """Fetch items from a source, dedupe, write markdown. Returns list of new items.
    
    If since is set (YYYY-MM-DD), skip items with a date before that.
    If conn is None, opens a per-call connection (for thread safety).
    """
    own_conn = conn is None
    if own_conn:
        conn = get_state_db(skill_dir)
    new_items = []
    try:
        raw_items = _fetch_with_retry(fetcher_fn, max_retries)
    except Exception as e:
        log_pipeline(skill_dir, f"ingest.{source_type}", "error",
                     source_id=source_id, error=str(e))
        return []

    for item in raw_items:
        # Date filter
        if since and item.get("date", "") and item["date"] < since:
            continue

        item_id = f"{source_type}-{item['id']}"
        seen = conn.execute(
            "SELECT 1 FROM seen_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        if seen:
            continue

        out_dir = skill_dir / "feeds" / "raw" / source_type / source_id
        out_dir.mkdir(parents=True, exist_ok=True)
        date_str = item.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        slug = slugify(item.get("title", item_id), max_length=80)
        out_path = out_dir / f"{date_str}_{slug}.md"

        frontmatter = {
            "item_id": item_id,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source_type": source_type,
            "source_id": source_id,
            "date": date_str,
        }
        fm_str = yaml.dump(frontmatter, default_flow_style=False).strip()
        content = item.get("content", "")
        md_content = f"---\n{fm_str}\n---\n\n{content}\n"

        out_path.write_text(md_content, encoding="utf-8")
        conn.execute(
            "INSERT INTO seen_items (item_id, source_type, source_id, date_seen) VALUES (?, ?, ?, ?)",
            (item_id, source_type, source_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        new_items.append({"item_id": item_id, "path": str(out_path), **item})

    status = "ok" if new_items else "no_new_items"
    log_pipeline(skill_dir, f"ingest.{source_type}", status,
                 source_id=source_id, new_count=len(new_items))
    if own_conn:
        conn.close()
    return new_items


def _fetch_with_retry(fn: Callable, max_retries: int) -> list[dict]:
    import time
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise last_err
